def test_admin_organizations_include_labels_and_ids(client, auth, fixtures):
    response = client.get('/api/organizations', headers=auth('admin'))
    assert response.status_code == 200
    rows = response.get_json()
    org_a = next(row for row in rows if row['id'] == fixtures['orgs']['a'])
    assert org_a['name'] == 'Org A Logging'
    assert org_a['registration_number'] == 'ORG-A'


def test_organizations_are_admin_only(client, auth):
    assert client.get('/api/organizations', headers=auth('fo_a')).status_code == 403
    assert client.get('/api/organizations/999999', headers=auth('admin')).status_code == 404


def test_organization_details_are_admin_only_and_not_found_is_controlled(client, auth, fixtures):
    assert client.get(
        f"/api/organizations/{fixtures['orgs']['b']}", headers=auth('fo_a')
    ).status_code == 403
    response = client.get(f"/api/organizations/{fixtures['orgs']['a']}", headers=auth('admin'))
    assert response.status_code == 200
    assert response.get_json()['name'] == 'Org A Logging'
    assert client.get('/api/organizations/999999', headers=auth('admin')).status_code == 404


def test_plot_options_include_owner_and_location(client, auth, fixtures):
    response = client.get('/api/forest-plots', headers=auth('fo_a'))
    assert response.status_code == 200
    plot = response.get_json()[0]
    assert plot['id'] == fixtures['plots']['a']
    assert plot['org_id'] == fixtures['orgs']['a']
    assert plot['location_lat'] == -0.5
    assert plot['location_lon'] == 35.4
    assert plot['approved_capacity_hectares'] == 120


def test_permit_options_include_status_and_core_fields(client, auth, fixtures):
    response = client.get('/api/permits?type=harvest', headers=auth('fo_a'))
    assert response.status_code == 200
    permit = next(row for row in response.get_json() if row['id'] == fixtures['permits']['a'])
    assert permit['permit_number'] == 'P-A'
    assert permit['type'] == 'harvest'
    assert permit['issue_date']
    assert permit['expiry_date']
    assert permit['status'] == 'active'


def test_permit_options_hide_expired_revoked_and_other_types(client, auth, fixtures):
    response = client.get('/api/permits?type=harvest', headers=auth('fo_a'))
    ids = {row['id'] for row in response.get_json()}
    assert fixtures['permits']['a'] in ids
    assert fixtures['permits']['expired'] not in ids
    assert fixtures['permits']['revoked'] not in ids
    assert fixtures['permits']['transport'] not in ids


def test_transporter_sees_only_own_vehicles(client, auth, fixtures):
    response = client.get('/api/vehicles', headers=auth('transporter'))
    assert response.status_code == 200
    rows = response.get_json()
    assert len(rows) == 1
    assert rows[0]['id'] == fixtures['vehicles']['transporter']
    assert rows[0]['plate_number'] == 'TEST-TRUCK-1'
    assert rows[0]['capacity_m3'] == 20


def test_user_endpoint_returns_current_organization(client, auth, fixtures):
    response = client.get('/api/me', headers=auth('fo_a'))
    assert response.status_code == 200
    assert response.get_json()['org_id'] == fixtures['orgs']['a']
    assert response.get_json()['organization']['name'] == 'Org A Logging'
