from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hashlib
import secrets

db = SQLAlchemy()


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)


class UserRole(db.Model):
    __tablename__ = 'user_roles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), primary_key=True)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    phone = db.Column(db.String(20))
    status = db.Column(db.String(20), default='active')
    last_login_at = db.Column(db.DateTime)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    roles = db.relationship('Role', secondary='user_roles', backref='users', lazy='joined')

    @property
    def role(self):
        if self.id is None:
            return None
        role_name = db.session.execute(
            db.select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == self.id)
            .limit(1)
        ).scalar()
        return role_name

    @role.setter
    def role(self, value):
        if not value:
            return

        normalized = str(value).strip().lower()
        if not normalized:
            return

        role = Role.query.filter_by(name=normalized).first()
        if not role:
            role = Role(name=normalized)
            db.session.add(role)
            db.session.flush()

        # The relationship owns the user_roles rows; adding them here as well double-inserts.
        self.roles = [role]

class Organization(db.Model):
    __tablename__ = 'organizations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(40), nullable=False)  # KFS, logger, transporter, mill, buyer
    registration_number = db.Column(db.String(60), unique=True)
    contact = db.Column(db.String(120))

class ForestPlot(db.Model):
    __tablename__ = 'forest_plots'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    forest_name = db.Column(db.String(120), nullable=False)
    location_lat = db.Column(db.Float)
    location_lon = db.Column(db.Float)
    approved_capacity_hectares = db.Column(db.Float)

class Permit(db.Model):
    __tablename__ = 'permits'
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    permit_number = db.Column(db.String(60), unique=True, nullable=False)
    type = db.Column(db.String(40), nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, expired, revoked

class TimberBatch(db.Model):
    __tablename__ = 'timber_batches'
    id = db.Column(db.Integer, primary_key=True)
    unique_tag_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    species = db.Column(db.String(120), nullable=False)
    volume_m3 = db.Column(db.Float, nullable=False)
    weight_kg = db.Column(db.Float)
    harvest_date = db.Column(db.Date)
    plot_id = db.Column(db.Integer, db.ForeignKey('forest_plots.id'))
    current_status = db.Column(db.String(40), default='harvested')  # harvested, in_transit, at_mill, sold
    current_holder_org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    permit_id = db.Column(db.Integer, db.ForeignKey('permits.id'))
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    source_org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    parent_batch_id = db.Column(db.Integer, db.ForeignKey('timber_batches.id'))
    qr_token_hash = db.Column(
        db.String(64),
        nullable=False,
        default=lambda: hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
    )
    qr_issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    qr_revoked_at = db.Column(db.DateTime)
    qr_code_path = db.Column(db.String(255))
    qr_code_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('timber_batches.id'), nullable=False)
    event_type = db.Column(db.String(30), nullable=False)  # harvest, load, unload, process, sale
    event_status = db.Column(db.String(20), nullable=False, default='confirmed')
    initiated_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    from_org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    to_org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'))
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'))
    permit_id = db.Column(db.Integer, db.ForeignKey('permits.id'))
    quantity_m3 = db.Column(db.Float)
    weight_kg = db.Column(db.Float)
    occurred_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    recorded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    location_lat = db.Column(db.Float)
    location_lon = db.Column(db.Float)
    location_accuracy_m = db.Column(db.Float)
    notes = db.Column(db.String(500))
    transaction_hash = db.Column(db.String(64))
    anchored_at = db.Column(db.DateTime)

class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(30), unique=True, nullable=False)
    owner_org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    capacity_m3 = db.Column(db.Float)
    current_location = db.Column(db.String(120))

class BlockchainBlock(db.Model):
    __tablename__ = 'blockchain_blocks'
    number = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    previous_hash = db.Column(db.String(64), nullable=False)
    transactions_hash = db.Column(db.String(64), nullable=False)
    nonce = db.Column(db.Integer, nullable=False)
    block_hash = db.Column(db.String(64), unique=True, nullable=False)
    metadata_json = db.Column(db.Text)


class BlockchainBlockTransaction(db.Model):
    __tablename__ = 'blockchain_block_transactions'
    __table_args__ = (db.UniqueConstraint('transaction_id', name='uq_block_transaction_id'),)
    block_number = db.Column(
        db.Integer,
        db.ForeignKey('blockchain_blocks.number'),
        primary_key=True,
    )
    transaction_id = db.Column(
        db.Integer,
        db.ForeignKey('transactions.id'),
        primary_key=True,
    )
    transaction_hash = db.Column(db.String(64), nullable=False)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(80), nullable=False)
    table_affected = db.Column(db.String(40))
    record_id = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(45))