from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(40), nullable=False)  # logger, transporter, mill, inspector, buyer, admin
    org_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    qr_code_path = db.Column(db.String(255))
    qr_code_data = db.Column(db.Text)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('timber_batches.id'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    type = db.Column(db.String(40), nullable=False)  # harvest, load, unload, process, sale
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    location_lat = db.Column(db.Float)
    location_lon = db.Column(db.Float)
    document_refs = db.Column(db.Text)  # JSON string of doc URLs/IDs

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

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(80), nullable=False)
    table_affected = db.Column(db.String(40))
    record_id = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(45))