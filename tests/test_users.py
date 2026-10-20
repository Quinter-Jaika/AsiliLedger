from models import AuditLog, Organization, Role, User, UserRole, db


def test_admin_registers_user_with_org_role_and_audit(client, auth, app, fixtures):
    response = client.post('/api/register', headers=auth('admin'), json={
        'name': 'New Transporter',
        'email': 'new-transporter@test.local',
        'password': 'StrongPass123!',
        'phone': '0700000099',
        'org_id': fixtures['orgs']['transporter'],
        'role': 'transporter',
    })
    assert response.status_code == 201, response.get_json()

    with app.app_context():
        user = User.query.filter_by(email='new-transporter@test.local').one()
        assert user.org_id == fixtures['orgs']['transporter']
        assert user.role == 'transporter'
        assert UserRole.query.filter_by(user_id=user.id).count() == 1
        assert AuditLog.query.filter_by(action='register', record_id=user.id).count() == 1


def test_duplicate_user_email_is_rejected(client, auth, fixtures):
    response = client.post('/api/register', headers=auth('admin'), json={
        'name': 'Duplicate',
        'email': 'fo.a@test.local',
        'password': 'StrongPass123!',
        'org_id': fixtures['orgs']['a'],
        'role': 'forestry_officer',
    })
    assert response.status_code == 400


def test_registration_rejects_unknown_org_and_role(client, auth):
    base = {
        'name': 'Invalid User',
        'email': 'invalid@test.local',
        'password': 'StrongPass123!',
        'org_id': 999999,
        'role': 'forestry_officer',
    }
    response = client.post('/api/register', headers=auth('admin'), json=base)
    assert response.status_code == 404

    base['email'] = 'invalid-role@test.local'
    base['org_id'] = None
    base['role'] = 'root'
    response = client.post('/api/register', headers=auth('admin'), json=base)
    assert response.status_code == 400


def test_non_admin_cannot_register_users(client, auth):
    response = client.post('/api/register', headers=auth('fo_a'), json={})
    assert response.status_code == 403
