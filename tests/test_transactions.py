from models import AuditLog, TimberBatch, Transaction, db


def _create_batch(client, auth, new_batch, tag='TX-BATCH-001', **overrides):
    response = client.post(
        '/api/batches',
        headers=auth('fo_a'),
        json=new_batch(unique_tag_id=tag, **overrides),
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def _event(client, auth, batch_id, event_type, **fields):
    return client.post(
        '/api/transactions',
        headers=auth,
        json={'batch_id': batch_id, 'type': event_type, **fields},
    )


def test_full_custody_lifecycle_uses_valid_state_transitions(app, client, auth, new_batch, fixtures):
    batch = _create_batch(client, auth, new_batch)
    batch_id = batch['id']

    load = _event(
        client, auth('transporter'), batch_id, 'load',
        to_org_id=fixtures['orgs']['transporter'],
        vehicle_id=fixtures['vehicles']['transporter'],
    )
    assert load.status_code == 201, load.get_json()

    unload = _event(
        client, auth('transporter'), batch_id, 'unload',
        to_org_id=fixtures['orgs']['mill'],
        vehicle_id=fixtures['vehicles']['transporter'],
    )
    assert unload.status_code == 201, unload.get_json()

    process = _event(
        client, auth('mill'), batch_id, 'process',
        to_org_id=fixtures['orgs']['mill'],
    )
    assert process.status_code == 201, process.get_json()

    sale = _event(
        client, auth('mill'), batch_id, 'sale',
        to_org_id=fixtures['orgs']['buyer'],
    )
    assert sale.status_code == 201, sale.get_json()

    with app.app_context():
        saved = db.session.get(TimberBatch, batch_id)
        assert saved.current_status == 'sold'
        assert saved.current_holder_org_id == fixtures['orgs']['buyer']
        txs = Transaction.query.filter_by(batch_id=batch_id).order_by(Transaction.occurred_at).all()
        assert [tx.event_type for tx in txs] == ['harvest', 'load', 'unload', 'process', 'sale']
        assert all(tx.transaction_hash for tx in txs)
        assert all(tx.initiated_by_user_id for tx in txs)


def test_unload_before_load_is_rejected(client, auth, new_batch, fixtures):
    batch = _create_batch(client, auth, new_batch)
    response = _event(
        client, auth('admin'), batch['id'], 'unload',
        to_org_id=fixtures['orgs']['mill'],
        vehicle_id=fixtures['vehicles']['transporter'],
    )
    assert response.status_code == 400


def test_process_before_mill_receipt_is_rejected(client, auth, new_batch, fixtures):
    batch = _create_batch(client, auth, new_batch)
    response = _event(
        client, auth('admin'), batch['id'], 'process',
        to_org_id=fixtures['orgs']['mill'],
    )
    assert response.status_code == 400


def test_sale_before_processing_is_rejected(client, auth, new_batch, fixtures):
    batch = _create_batch(client, auth, new_batch)
    response = _event(
        client, auth('admin'), batch['id'], 'sale',
        to_org_id=fixtures['orgs']['buyer'],
    )
    assert response.status_code == 400


def test_load_after_sale_is_rejected(client, auth, new_batch, fixtures):
    batch = _create_batch(client, auth, new_batch)
    batch_id = batch['id']
    for event_type, user_key, destination in [
        ('load', 'transporter', fixtures['orgs']['transporter']),
        ('unload', 'transporter', fixtures['orgs']['mill']),
        ('process', 'mill', fixtures['orgs']['mill']),
        ('sale', 'mill', fixtures['orgs']['buyer']),
    ]:
        response = _event(
            client, auth(user_key), batch_id, event_type,
            to_org_id=destination,
            **({'vehicle_id': fixtures['vehicles']['transporter']} if event_type in ('load', 'unload') else {}),
        )
        assert response.status_code == 201, response.get_json()

    response = _event(
        client, auth('admin'), batch_id, 'load',
        to_org_id=fixtures['orgs']['transporter'],
        vehicle_id=fixtures['vehicles']['transporter'],
    )
    assert response.status_code == 400


def test_only_transporter_can_load(client, auth, new_batch, fixtures):
    batch = _create_batch(client, auth, new_batch)
    response = _event(
        client, auth('fo_a'), batch['id'], 'load',
        to_org_id=fixtures['orgs']['transporter'],
        vehicle_id=fixtures['vehicles']['transporter'],
    )
    assert response.status_code == 403


def test_non_holder_mill_cannot_process_batch(client, auth, new_batch, fixtures, app):
    batch = _create_batch(client, auth, new_batch)
    load = _event(
        client, auth('transporter'), batch['id'], 'load',
        to_org_id=fixtures['orgs']['transporter'],
        vehicle_id=fixtures['vehicles']['transporter'],
    )
    assert load.status_code == 201
    unload = _event(
        client, auth('transporter'), batch['id'], 'unload',
        to_org_id=fixtures['orgs']['mill'],
        vehicle_id=fixtures['vehicles']['transporter'],
    )
    assert unload.status_code == 201

    with app.app_context():
        batch_row = db.session.get(TimberBatch, batch['id'])
        batch_row.current_holder_org_id = fixtures['orgs']['b']
        db.session.commit()

    response = _event(
        client, auth('mill'), batch['id'], 'process',
        to_org_id=fixtures['orgs']['b'],
    )
    assert response.status_code == 403


def test_buyer_cannot_create_transactions(client, auth, new_batch, fixtures):
    batch = _create_batch(client, auth, new_batch)
    response = _event(
        client, auth('buyer'), batch['id'], 'load',
        to_org_id=fixtures['orgs']['transporter'],
    )
    assert response.status_code == 403


def test_foreign_vehicle_is_rejected(client, auth, new_batch, fixtures):
    batch = _create_batch(client, auth, new_batch)
    response = _event(
        client, auth('transporter'), batch['id'], 'load',
        to_org_id=fixtures['orgs']['transporter'],
        vehicle_id=fixtures['vehicles']['foreign'],
    )
    assert response.status_code == 403


def test_invalid_vehicle_and_destination_return_controlled_errors(client, auth, new_batch, fixtures):
    batch = _create_batch(client, auth, new_batch)
    invalid_vehicle = _event(
        client, auth('transporter'), batch['id'], 'load',
        to_org_id=fixtures['orgs']['transporter'], vehicle_id=999999,
    )
    assert invalid_vehicle.status_code == 404

    invalid_org = _event(
        client, auth('transporter'), batch['id'], 'load',
        to_org_id=999999, vehicle_id=fixtures['vehicles']['transporter'],
    )
    assert invalid_org.status_code == 404


def test_vehicle_capacity_must_cover_batch_volume(client, auth, new_batch, fixtures):
    batch = _create_batch(client, auth, new_batch, volume_m3=25)
    response = _event(
        client, auth('transporter'), batch['id'], 'load',
        to_org_id=fixtures['orgs']['transporter'],
        vehicle_id=fixtures['vehicles']['transporter'],
    )
    assert response.status_code == 400


def test_invalid_batch_id_query_returns_bad_request(client, auth):
    response = client.get('/api/transactions?batch_id=not-an-id', headers=auth('transporter'))
    assert response.status_code == 400


def test_unknown_transaction_id_returns_not_found(client, auth):
    response = client.get('/api/transactions/999999', headers=auth('transporter'))
    assert response.status_code == 404


def test_batch_creation_writes_audit_record(app, client, auth, new_batch, fixtures):
    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch())
    assert response.status_code == 201

    with app.app_context():
        entry = AuditLog.query.filter_by(
            action='create_batch', record_id=response.get_json()['id']
        ).one()
        assert entry.user_id == fixtures['users']['fo_a']
        assert entry.table_affected == 'timber_batches'
        assert entry.ip_address


def test_harvest_transaction_uses_plot_location_and_permit(app, client, auth, new_batch, fixtures):
    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch())
    assert response.status_code == 201

    with app.app_context():
        tx = Transaction.query.filter_by(batch_id=response.get_json()['id']).one()
        assert tx.permit_id == fixtures['permits']['a']
        assert tx.location_lat == -0.5
        assert tx.location_lon == 35.4
        assert tx.from_user_id == fixtures['users']['fo_a']
        assert tx.to_user_id == fixtures['users']['fo_a']
