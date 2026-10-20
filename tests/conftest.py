import os
import sys
import tempfile
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from auth import hash_password
from blockchain import initialize_chain, reset_chain_state
from models import db, ForestPlot, Organization, Permit, User, Vehicle

PASSWORD = 'Passw0rd!'


def _make_user(name, email, org_id, role):
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(PASSWORD),
        org_id=org_id,
        status='active',
    )
    db.session.add(user)
    db.session.commit()
    user.role = role
    db.session.commit()
    return user


def _seed():
    org_a = Organization(name='Org A Logging', type='logger', registration_number='ORG-A')
    org_b = Organization(name='Org B Logging', type='logger', registration_number='ORG-B')
    org_admin = Organization(name='Regulator', type='admin', registration_number='ORG-ADMIN')
    org_transport = Organization(name='Transport Co', type='transporter', registration_number='ORG-TRANSPORT')
    org_mill = Organization(name='Mill Co', type='mill', registration_number='ORG-MILL')
    org_buyer = Organization(name='Buyer Co', type='buyer', registration_number='ORG-BUYER')
    org_inspector = Organization(name='Inspectorate', type='inspector', registration_number='ORG-INSPECTOR')
    db.session.add_all([org_a, org_b, org_admin, org_transport, org_mill, org_buyer, org_inspector])
    db.session.commit()

    plot_a = ForestPlot(org_id=org_a.id, forest_name='Plot A', location_lat=-0.5, location_lon=35.4,
                        approved_capacity_hectares=120.0)
    plot_b = ForestPlot(org_id=org_b.id, forest_name='Plot B', location_lat=0.3, location_lon=34.7)
    db.session.add_all([plot_a, plot_b])

    today = date.today()
    permits = {
        'a': Permit(org_id=org_a.id, permit_number='P-A', type='harvest',
                    issue_date=today - timedelta(days=30), expiry_date=today + timedelta(days=90),
                    status='active'),
        'b': Permit(org_id=org_b.id, permit_number='P-B', type='harvest',
                    issue_date=today - timedelta(days=30), expiry_date=today + timedelta(days=90),
                    status='active'),
        'expired': Permit(org_id=org_a.id, permit_number='P-A-EXPIRED', type='harvest',
                          issue_date=today - timedelta(days=400), expiry_date=today - timedelta(days=1),
                          status='active'),
        'revoked': Permit(org_id=org_a.id, permit_number='P-A-REVOKED', type='harvest',
                          issue_date=today - timedelta(days=30), expiry_date=today + timedelta(days=90),
                          status='revoked'),
        'transport': Permit(org_id=org_a.id, permit_number='P-A-TRANSPORT', type='transport',
                            issue_date=today - timedelta(days=30), expiry_date=today + timedelta(days=90),
                            status='active'),
    }
    db.session.add_all(permits.values())
    db.session.commit()

    users = {
        'admin': _make_user('Admin', 'admin@test.local', org_admin.id, 'admin'),
        'fo_a': _make_user('Officer A', 'fo.a@test.local', org_a.id, 'forestry_officer'),
        'fo_b': _make_user('Officer B', 'fo.b@test.local', org_b.id, 'forestry_officer'),
        'transporter': _make_user('Driver', 'driver@test.local', org_transport.id, 'transporter'),
        'mill': _make_user('Mill Operator', 'mill@test.local', org_mill.id, 'mill'),
        'buyer': _make_user('Buyer', 'buyer@test.local', org_buyer.id, 'buyer'),
        'inspector': _make_user('Inspector', 'inspector@test.local', org_inspector.id, 'inspector'),
    }
    vehicle = Vehicle(
        owner_org_id=org_transport.id,
        plate_number='TEST-TRUCK-1',
        capacity_m3=20.0,
        current_location='Test Yard',
    )
    foreign_vehicle = Vehicle(
        owner_org_id=org_b.id,
        plate_number='TEST-TRUCK-2',
        capacity_m3=50.0,
        current_location='Other Yard',
    )
    db.session.add_all([vehicle, foreign_vehicle])
    db.session.commit()

    return {
        'orgs': {
            'a': org_a.id,
            'b': org_b.id,
            'admin': org_admin.id,
            'transporter': org_transport.id,
            'mill': org_mill.id,
            'buyer': org_buyer.id,
            'inspector': org_inspector.id,
        },
        'plots': {'a': plot_a.id, 'b': plot_b.id},
        'permits': {key: permit.id for key, permit in permits.items()},
        'users': {key: user.id for key, user in users.items()},
        'emails': {key: user.email for key, user in users.items()},
        'vehicles': {'transporter': vehicle.id, 'foreign': foreign_vehicle.id},
    }


@pytest.fixture
def app():
    handle, path = tempfile.mkstemp(suffix='.db')
    os.close(handle)

    application = create_app({
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{path}',
        'TESTING': True,
    })

    with application.app_context():
        db.drop_all()
        db.create_all()
        reset_chain_state()
        initialize_chain()
        application.config['FIXTURES'] = _seed()

    yield application

    os.unlink(path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fixtures(app):
    return app.config['FIXTURES']


@pytest.fixture
def auth(client, fixtures):
    def _auth(user_key):
        response = client.post('/api/login', json={
            'email': fixtures['emails'][user_key],
            'password': PASSWORD,
        })
        assert response.status_code == 200, response.get_json()
        return {'Authorization': 'Bearer ' + response.get_json()['token']}

    return _auth


@pytest.fixture
def new_batch(fixtures):
    def _payload(**overrides):
        payload = {
            'unique_tag_id': 'BATCH-001',
            'species': 'Mahogany',
            'volume_m3': 10.5,
            'weight_kg': 7000,
            'harvest_date': date.today().isoformat(),
            'plot_id': fixtures['plots']['a'],
            'permit_id': fixtures['permits']['a'],
        }
        payload.update(overrides)
        return payload

    return _payload
