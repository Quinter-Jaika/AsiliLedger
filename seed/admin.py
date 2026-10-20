import sys
sys.path.insert(0, '.')

from app import create_app
from models import db, User, Organization, AuditLog, Role, UserRole
from auth import hash_password


def main():
    app = create_app()
    with app.app_context():
        db.create_all()

        org = Organization.query.filter_by(type='admin').first()
        if not org:
            org = Organization(
                name='System Admin',
                type='admin',
                registration_number='SYS-001'
            )
            db.session.add(org)
            db.session.commit()

        admin_email = 'admin@asililedger.local'
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(
                name='System Administrator',
                email=admin_email,
                password_hash=hash_password('Admin123!'),
                org_id=org.id,
                phone='0700000000'
            )
            db.session.add(admin)
            db.session.commit()

        role = Role.query.filter_by(name='admin').first()
        if not role:
            role = Role(name='admin')
            db.session.add(role)
            db.session.commit()

        if not UserRole.query.filter_by(user_id=admin.id, role_id=role.id).first():
            db.session.add(UserRole(user_id=admin.id, role_id=role.id))
            db.session.commit()

        entry = AuditLog(
            user_id=admin.id,
            action='seed_admin_created',
            table_affected='users',
            record_id=admin.id,
            ip_address='127.0.0.1'
        )
        db.session.add(entry)
        db.session.commit()

        print(f"Admin created: {admin.email} / role=admin")
        print("LOGIN: email=admin@asililedger.local  password=Admin123!")
        print("⚠️ Change this password after first login.")


if __name__ == '__main__':
    main()