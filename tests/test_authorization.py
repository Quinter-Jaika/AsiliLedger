def _create_batch(client, auth, new_batch, user_key='fo_a', **overrides):
    response = client.post('/api/batches', headers=auth(user_key), json=new_batch(**overrides))
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def test_unauthenticated_requests_rejected(client):
    assert client.get('/api/batches').status_code == 401
    assert client.get('/api/forest-plots').status_code == 401


def test_transporter_cannot_create_batch(client, auth, new_batch):
    response = client.post('/api/batches', headers=auth('transporter'), json=new_batch())
    assert response.status_code == 403


def test_officer_cannot_read_other_org_batch(client, auth, new_batch, fixtures):
    created = _create_batch(client, auth, new_batch, 'fo_a')

    response = client.get(f"/api/batches/{created['id']}/verify", headers=auth('fo_b'))
    assert response.status_code == 403, response.get_json()


def test_buyer_cannot_read_batch_without_custody_relationship(client, auth, new_batch):
    created = _create_batch(client, auth, new_batch, 'fo_a')
    response = client.get(
        f"/api/batches/by-tag/{created['unique_tag_id']}",
        headers=auth('buyer'),
    )
    assert response.status_code == 403


def test_officer_cannot_read_other_org_batch_by_tag(client, auth, new_batch):
    created = _create_batch(client, auth, new_batch, 'fo_a')

    response = client.get(f"/api/batches/by-tag/{created['unique_tag_id']}", headers=auth('fo_b'))
    assert response.status_code == 403


def test_officer_cannot_read_other_org_transaction_by_id(client, auth, new_batch):
    created = _create_batch(client, auth, new_batch, 'fo_a')
    response = client.get(
        f"/api/transactions/{created['harvest_transaction_id']}",
        headers=auth('fo_b'),
    )
    assert response.status_code in (403, 404)


def test_officer_cannot_download_another_org_qr(client, auth, new_batch):
    created = _create_batch(client, auth, new_batch, 'fo_a')
    response = client.get(f"/api/batches/{created['id']}/qr/download", headers=auth('fo_b'))
    assert response.status_code == 403


def test_officer_sees_only_own_org_plots(client, auth, fixtures):
    response = client.get('/api/forest-plots', headers=auth('fo_a'))
    assert response.status_code == 200
    assert {plot['id'] for plot in response.get_json()} == {fixtures['plots']['a']}


def test_officer_sees_only_own_valid_permits(client, auth, fixtures):
    response = client.get('/api/permits?type=harvest', headers=auth('fo_a'))
    assert response.status_code == 200
    assert {p['id'] for p in response.get_json()} == {fixtures['permits']['a']}


def test_admin_sees_all_plots(client, auth, fixtures):
    response = client.get('/api/forest-plots', headers=auth('admin'))
    assert response.status_code == 200
    assert {plot['id'] for plot in response.get_json()} == set(fixtures['plots'].values())


def test_batch_list_is_scoped_for_forestry_officers(client, auth, new_batch):
    _create_batch(client, auth, new_batch, 'fo_a', unique_tag_id='BATCH-A')
    _create_batch(client, auth, new_batch, 'fo_b', unique_tag_id='BATCH-B', plot_id=2, permit_id=2)

    own_rows = client.get('/api/batches', headers=auth('fo_a')).get_json()
    other_rows = client.get('/api/batches', headers=auth('fo_b')).get_json()
    assert [row['unique_tag_id'] for row in own_rows] == ['BATCH-A']
    assert [row['unique_tag_id'] for row in other_rows] == ['BATCH-B']


def test_non_admin_cannot_list_organizations(client, auth):
    assert client.get('/api/organizations', headers=auth('fo_a')).status_code == 403
    assert client.get('/api/organizations', headers=auth('admin')).status_code == 200


def test_scan_token_resolves_for_permitted_user(client, auth, new_batch):
    created = _create_batch(client, auth, new_batch, 'fo_a')
    token = created['scan_url'].rstrip('/').split('/')[-1]

    response = client.get(f'/api/scan/{token}', headers=auth('fo_a'))
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['unique_tag_id'] == created['unique_tag_id']


def test_invalid_scan_token_returns_not_found(client, auth):
    response = client.get('/api/scan/not-a-real-token', headers=auth('fo_a'))
    assert response.status_code == 404


def test_scan_token_rejected_for_other_org(client, auth, new_batch):
    created = _create_batch(client, auth, new_batch, 'fo_a')
    token = created['scan_url'].rstrip('/').split('/')[-1]

    response = client.get(f'/api/scan/{token}', headers=auth('fo_b'))
    assert response.status_code == 403


def test_rotating_qr_invalidates_previous_token(client, auth, new_batch):
    created = _create_batch(client, auth, new_batch, 'fo_a')
    old_token = created['scan_url'].rstrip('/').split('/')[-1]

    rotated = client.post(f"/api/batches/{created['id']}/qr/rotate", headers=auth('fo_a'))
    assert rotated.status_code == 200, rotated.get_json()
    new_token = rotated.get_json()['scan_url'].rstrip('/').split('/')[-1]

    assert new_token != old_token
    assert client.get(f'/api/scan/{old_token}', headers=auth('fo_a')).status_code == 404
    assert client.get(f'/api/scan/{new_token}', headers=auth('fo_a')).status_code == 200


def test_scan_landing_page_exposes_no_batch_data(client, auth, new_batch):
    created = _create_batch(client, auth, new_batch, 'fo_a')
    token = created['scan_url'].rstrip('/').split('/')[-1]

    page = client.get(f'/scan/{token}')
    assert page.status_code == 200
    assert created['unique_tag_id'].encode() not in page.data


def test_revoked_qr_token_cannot_resolve(client, auth, new_batch):
    created = _create_batch(client, auth, new_batch, 'fo_a')
    token = created['scan_url'].rstrip('/').split('/')[-1]

    revoked = client.post(f"/api/batches/{created['id']}/qr/revoke", headers=auth('fo_a'))
    assert revoked.status_code == 200, revoked.get_json()
    assert client.get(f'/api/scan/{token}', headers=auth('fo_a')).status_code == 404


def test_scan_page_prompts_login_when_signed_out(client):
    response = client.get('/scan/a-long-random-token')
    assert response.status_code == 200
    assert b'Please sign in to view this batch' in response.data
    assert b'/?next=' in response.data
