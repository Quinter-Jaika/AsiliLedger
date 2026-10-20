from common import run_seed
from auth import hash_password
from models import db, Organization, Role, User, UserRole
from organizations import seed_organizations


USERS = [
    {
        'name': 'Forestry Officer',
        'email': 'logger@asililedger.local',
        'password': 'Logger123!',
        'organization_registration_number': 'LOG-001',
        'phone': '0700000001',
        'role': 'forestry_officer',
    },
    {
        'name': 'Transport Coordinator',
        'email': 'transporter@asililedger.local',
        'password': 'Transporter123!',
        'organization_registration_number': 'TRN-001',
        'phone': '0700000002',
        'role': 'transporter',
    },
    {
        'name': 'Mill Operator',
        'email': 'mill@asililedger.local',
        'password': 'Mill123!',
        'organization_registration_number': 'MIL-001',
        'phone': '0700000003',
        'role': 'mill',
    },
    {
        'name': 'Supply Chain Inspector',
        'email': 'inspector@asililedger.local',
        'password': 'Inspector123!',
        'organization_registration_number': 'KFS-001',
        'phone': '0700000004',
        'role': 'inspector',
    },
    {
        'name': 'Timber Buyer',
        'email': 'buyer@asililedger.local',
        'password': 'Buyer123!',
        'organization_registration_number': 'BUY-001',
        'phone': '0700000005',
        'role': 'buyer',
    },
]


def seed_users():
    seed_organizations()
    for user_data in USERS:
        organization = Organization.query.filter_by(
            registration_number=user_data['organization_registration_number']
        ).one()
        user = User.query.filter_by(email=user_data['email']).first()
        if user is None:
            user = User(
                name=user_data['name'],
                email=user_data['email'],
                password_hash=hash_password(user_data['password']),
                org_id=organization.id,
                phone=user_data['phone'],
                status='active',
            )
            db.session.add(user)
        else:
            user.name = user_data['name']
            user.org_id = organization.id
            user.phone = user_data['phone']
            user.status = 'active'

        role = Role.query.filter_by(name=user_data['role']).first()
        if role is None:
            role = Role(name=user_data['role'])
            db.session.add(role)
        db.session.flush()
        db_user_role = UserRole.query.filter_by(
            user_id=user.id,
            role_id=role.id,
        ).first()
        if db_user_role is None:
            db.session.add(UserRole(user_id=user.id, role_id=role.id))
    return len(USERS)


if __name__ == '__main__':
    run_seed(seed_users)
