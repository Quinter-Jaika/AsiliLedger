import hashlib
from datetime import date, timedelta

from models import TimberBatch, Transaction, db


def test_admin_can_create_batch(client, auth, new_batch):
    response = client.post('/api/batches', headers=auth('admin'), json=new_batch())
    assert response.status_code == 201, response.get_json()
    assert response.get_json()['batch']['current_status'] == 'harvested'


def test_forestry_officer_can_create_batch_for_own_org(client, auth, new_batch, fixtures):
    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch())
    assert response.status_code == 201, response.get_json()
    assert response.get_json()['batch']['current_holder_org_id'] == fixtures['orgs']['a']


def test_officer_cannot_use_another_orgs_plot(client, auth, new_batch, fixtures):
    payload = new_batch(plot_id=fixtures['plots']['b'], permit_id=fixtures['permits']['a'])
    response = client.post('/api/batches', headers=auth('fo_a'), json=payload)
    assert response.status_code == 403, response.get_json()


def test_officer_cannot_use_another_orgs_permit(client, auth, new_batch, fixtures):
    payload = new_batch(permit_id=fixtures['permits']['b'])
    response = client.post('/api/batches', headers=auth('fo_a'), json=payload)
    assert response.status_code == 403, response.get_json()


def test_duplicate_tag_returns_conflict(client, auth, new_batch):
    assert client.post('/api/batches', headers=auth('fo_a'), json=new_batch()).status_code == 201
    repeat = client.post('/api/batches', headers=auth('fo_a'), json=new_batch())
    assert repeat.status_code == 409, repeat.get_json()


def test_missing_fields_return_bad_request(client, auth):
    response = client.post('/api/batches', headers=auth('fo_a'), json={'species': 'Teak'})
    assert response.status_code == 400
    assert set(response.get_json()['fields']) >= {'unique_tag_id', 'volume_m3', 'harvest_date', 'plot_id', 'permit_id'}


def test_harvest_permit_is_required(client, auth, new_batch):
    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch(permit_id=None))
    assert response.status_code == 400
    assert 'permit_id' in response.get_json()['fields']


def test_expired_permit_rejected(client, auth, new_batch, fixtures):
    payload = new_batch(permit_id=fixtures['permits']['expired'])
    response = client.post('/api/batches', headers=auth('fo_a'), json=payload)
    assert response.status_code == 400
    assert 'expired' in response.get_json()['error'].lower()


def test_revoked_permit_rejected(client, auth, new_batch, fixtures):
    payload = new_batch(permit_id=fixtures['permits']['revoked'])
    response = client.post('/api/batches', headers=auth('fo_a'), json=payload)
    assert response.status_code == 400
    assert 'not active' in response.get_json()['error'].lower()


def test_wrong_permit_type_rejected(client, auth, new_batch, fixtures):
    payload = new_batch(permit_id=fixtures['permits']['transport'])
    response = client.post('/api/batches', headers=auth('fo_a'), json=payload)
    assert response.status_code == 400


def test_unknown_plot_returns_not_found(client, auth, new_batch):
    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch(plot_id=999999))
    assert response.status_code == 404


def test_non_positive_volume_rejected(client, auth, new_batch):
    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch(volume_m3=0))
    assert response.status_code == 400


def test_negative_weight_rejected(client, auth, new_batch):
    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch(weight_kg=-5))
    assert response.status_code == 400


def test_future_harvest_date_rejected(client, auth, new_batch):
    future = (date.today() + timedelta(days=2)).isoformat()
    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch(harvest_date=future))
    assert response.status_code == 400


def test_client_cannot_override_status_or_holder(app, client, auth, new_batch, fixtures):
    payload = new_batch(current_status='sold', current_holder_org_id=fixtures['orgs']['b'])
    response = client.post('/api/batches', headers=auth('fo_a'), json=payload)
    assert response.status_code == 201

    with app.app_context():
        batch = db.session.get(TimberBatch, response.get_json()['id'])
        assert batch.current_status == 'harvested'
        assert batch.current_holder_org_id == fixtures['orgs']['a']


def test_harvest_transaction_created_from_token_user(app, client, auth, new_batch, fixtures):
    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch())
    batch_id = response.get_json()['id']

    with app.app_context():
        txs = Transaction.query.filter_by(batch_id=batch_id).all()
        assert len(txs) == 1
        assert txs[0].event_type == 'harvest'
        assert txs[0].initiated_by_user_id == fixtures['users']['fo_a']
        assert txs[0].transaction_hash


def test_only_token_hash_is_stored(app, client, auth, new_batch):
    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch())
    body = response.get_json()
    raw_token = body['scan_url'].rstrip('/').split('/')[-1]

    with app.app_context():
        batch = db.session.get(TimberBatch, body['id'])
        assert batch.qr_token_hash != raw_token
        assert batch.qr_token_hash == hashlib.sha256(raw_token.encode()).hexdigest()


def test_empty_tag_species_plot_and_harvest_date_are_rejected(client, auth, new_batch):
    for overrides in (
        {'unique_tag_id': ''},
        {'species': ''},
        {'plot_id': ''},
        {'harvest_date': ''},
    ):
        response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch(**overrides))
        assert response.status_code == 400, (overrides, response.get_json())


def test_negative_volume_and_non_numeric_values_are_rejected(client, auth, new_batch):
    for volume in (-0.1, 'not-a-number', 'NaN', 'Infinity'):
        response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch(volume_m3=volume))
        assert response.status_code == 400, (volume, response.get_json())

    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch(weight_kg='heavy'))
    assert response.status_code == 400


def test_tag_is_normalized_and_overlong_values_are_rejected(client, auth, new_batch):
    response = client.post(
        '/api/batches', headers=auth('fo_a'),
        json=new_batch(unique_tag_id='  ken-2026-001  '),
    )
    assert response.status_code == 201
    assert response.get_json()['unique_tag_id'] == 'KEN-2026-001'

    too_long = client.post(
        '/api/batches', headers=auth('fo_a'),
        json=new_batch(unique_tag_id='X' * 65),
    )
    assert too_long.status_code == 400

    long_species = client.post(
        '/api/batches', headers=auth('fo_a'),
        json=new_batch(unique_tag_id='BATCH-LONG-SPECIES', species='S' * 121),
    )
    assert long_species.status_code == 400


def test_qr_download_is_png_and_redownload_keeps_token(app, client, auth, new_batch):
    created = client.post('/api/batches', headers=auth('fo_a'), json=new_batch()).get_json()
    token = created['scan_url'].rstrip('/').split('/')[-1]

    first = client.get(f"/api/batches/{created['id']}/qr/download", headers=auth('fo_a'))
    assert first.status_code == 200
    assert first.mimetype == 'image/png'
    assert first.headers['Content-Disposition'].endswith('.png')

    second = client.get(f"/api/batches/{created['id']}/qr-data", headers=auth('fo_a'))
    assert second.status_code == 200
    assert second.get_json()['qr_code']

    with app.app_context():
        batch = db.session.get(TimberBatch, created['id'])
        assert batch.qr_token_hash == hashlib.sha256(token.encode()).hexdigest()


def test_script_like_species_is_stored_as_text(client, auth, new_batch, app):
    payload = new_batch(species='<script>alert(1)</script>')
    response = client.post('/api/batches', headers=auth('fo_a'), json=payload)
    assert response.status_code == 201
    assert response.mimetype == 'application/json'

    with app.app_context():
        batch = db.session.get(TimberBatch, response.get_json()['id'])
        assert batch.species == '<script>alert(1)</script>'
