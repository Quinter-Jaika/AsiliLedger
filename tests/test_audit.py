from models import AuditLog, db


def test_only_admin_can_view_audit_history(client, auth, app, fixtures):
    with app.app_context():
        db.session.add(AuditLog(
            user_id=fixtures['users']['fo_a'],
            action='test_action',
            table_affected='timber_batches',
            record_id=1,
            ip_address='127.0.0.1',
        ))
        db.session.commit()

    assert client.get('/api/audit-logs', headers=auth('fo_a')).status_code == 403
    response = client.get('/api/audit-logs', headers=auth('admin'))
    assert response.status_code == 200
    row = next(item for item in response.get_json() if item['action'] == 'test_action')
    assert row['user_id'] == fixtures['users']['fo_a']
    assert row['table_affected'] == 'timber_batches'
    assert row['timestamp']
    assert row['ip_address'] == '127.0.0.1'


def test_audit_history_pagination_is_bounded(client, auth):
    assert client.get('/api/audit-logs?limit=501', headers=auth('admin')).status_code == 400
    assert client.get('/api/audit-logs?limit=nope', headers=auth('admin')).status_code == 400
    response = client.get('/api/audit-logs?limit=1&offset=0', headers=auth('admin'))
    assert response.status_code == 200
    assert len(response.get_json()) <= 1
