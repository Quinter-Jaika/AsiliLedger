import base64
import hashlib
import json
import math
import os
import secrets
from io import BytesIO

import qrcode
from flask import Blueprint, request, jsonify, current_app, url_for, send_file
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from models import db, TimberBatch, Transaction, ForestPlot, Organization
from auth import log_audit, role_required
from permissions import can_access_batch, can_access_permit, can_access_plot, get_current_user
from blockchain import anchor_pending
from datetime import date, datetime
from werkzeug.utils import secure_filename
from transaction_utils import hash_transaction

batches_bp = Blueprint('batches', __name__)


def _normalize_species(data):
        raw_species = data.get('species')
        species = raw_species.strip() if isinstance(raw_species, str) else ''
        species_list = data.get('species_list')

        if isinstance(species_list, str):
                species_candidates = [s.strip() for s in species_list.split(',') if s.strip()]
        elif isinstance(species_list, list):
                species_candidates = [str(s).strip() for s in species_list if str(s).strip()]
        else:
                species_candidates = []

        if species == '__MULTIPLE__' or len(species_candidates) > 1:
                return ', '.join(species_candidates) if species_candidates else None

        if species_candidates:
                return species_candidates[0]

        return species or None

@batches_bp.route('/batches', methods=['GET'])
@role_required('admin', 'forestry_officer', 'transporter', 'mill')
def list_batches():
    user = get_current_user()
    query = TimberBatch.query
    role = (user.role or '').lower() if user else ''
    if role == 'forestry_officer':
        query = query.filter(or_(
            TimberBatch.created_by_user_id == user.id,
            TimberBatch.current_holder_org_id == user.org_id,
            TimberBatch.source_org_id == user.org_id,
        ))
    elif role in {'transporter', 'mill'}:
        related_batch_ids = db.session.query(Transaction.batch_id).filter(or_(
            Transaction.from_org_id == user.org_id,
            Transaction.to_org_id == user.org_id,
        ))
        query = query.filter(or_(
            TimberBatch.current_holder_org_id == user.org_id,
            TimberBatch.id.in_(related_batch_ids),
        ))
    rows = query.order_by(TimberBatch.id.desc()).all()
    return jsonify([{
      'id': r.id, 'unique_tag_id': r.unique_tag_id, 'species': r.species,
      'volume_m3': r.volume_m3, 'current_status': r.current_status,
      'qr_code_path': r.qr_code_path,
    'qr_code_url': url_for('batches.get_qr_code', batch_id=r.id, _external=True),
    'qr_data_url': url_for('batches.get_qr_code_data', batch_id=r.id, _external=True)
    } for r in rows])


@batches_bp.route('/batches/by-tag/<string:tag_id>', methods=['GET'])
@role_required('admin', 'forestry_officer', 'transporter', 'mill', 'inspector', 'buyer')
def get_batch_by_tag(tag_id):
    """Lookup batch details by unique tag id for authenticated scanning/track flows."""
    batch = TimberBatch.query.filter_by(unique_tag_id=tag_id).first()
    if not batch:
        return jsonify({'error': 'batch not found'}), 404

    _, error = can_access_batch(
        get_current_user(), 
        batch.id, 
        allow_unassigned_load=True
        )

    if error:
        return error

    plot = db.session.get(ForestPlot, batch.plot_id) if batch.plot_id else None
    holder = db.session.get(Organization, batch.current_holder_org_id) if batch.current_holder_org_id else None

    return jsonify({
        'id': batch.id,
        'unique_tag_id': batch.unique_tag_id,
        'species': batch.species,
        'volume_m3': batch.volume_m3,
        'weight_kg': batch.weight_kg,
        'current_status': batch.current_status,
        'current_holder_org_id': batch.current_holder_org_id,
        'current_holder_name': holder.name if holder else None,
        'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
        'plot': {
            'id': plot.id,
            'name': plot.forest_name,
            'location_lat': plot.location_lat,
            'location_lon': plot.location_lon,
            'approved_capacity_hectares': plot.approved_capacity_hectares,
        } if plot else None,
        'qr_code_url': url_for('batches.get_qr_code', batch_id=batch.id, _external=True),
        'qr_data_url': url_for('batches.get_qr_code_data', batch_id=batch.id, _external=True),
    })

@batches_bp.route('/batches', methods=['POST'])
@role_required('admin', 'forestry_officer')
def create_batch():
    data = request.get_json(silent=True) or {}
    user = get_current_user()

    normalized_species = _normalize_species(data)
    missing = [f for f in ('unique_tag_id', 'volume_m3', 'harvest_date', 'plot_id', 'permit_id')
               if data.get(f) in (None, '', [])]
    if not normalized_species:
        missing.append('species')
    if missing:
        return jsonify({'error': 'Missing required fields', 'fields': missing}), 400

    tag_id = str(data['unique_tag_id']).strip().upper()
    if not tag_id:
        return jsonify({'error': 'Batch tag is required'}), 400
    if not isinstance(data['unique_tag_id'], str):
        return jsonify({'error': 'Batch tag must be text'}), 400
    if len(tag_id) > 64 or len(normalized_species) > 120:
        return jsonify({'error': 'Batch tag or species exceeds its maximum length'}), 400

    try:
        volume_m3 = float(data['volume_m3'])
        weight_kg = float(data['weight_kg']) if data.get('weight_kg') not in (None, '') else None
        plot_id = int(data['plot_id'])
        permit_id = int(data['permit_id']) if data.get('permit_id') not in (None, '') else None
        harvest_date = datetime.strptime(data['harvest_date'], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid number, date, plot, or permit value'}), 400

    if not math.isfinite(volume_m3) or volume_m3 <= 0:
        return jsonify({'error': 'Volume must be greater than zero'}), 400
    if weight_kg is not None and (not math.isfinite(weight_kg) or weight_kg < 0):
        return jsonify({'error': 'Weight must be finite and cannot be negative'}), 400
    if harvest_date > date.today():
        return jsonify({'error': 'Harvest date cannot be in the future'}), 400

    if TimberBatch.query.filter_by(unique_tag_id=tag_id).first():
        return jsonify({'error': 'A timber batch already uses this tag'}), 409

    plot, plot_error = can_access_plot(user, plot_id)
    if plot_error:
        return plot_error

    permit = None
    if permit_id is not None:
        permit, permit_error = can_access_permit(user, permit_id, required_type='harvest')
        if permit_error:
            return permit_error
        if permit.org_id != plot.org_id:
            return jsonify({
                'error': 'The selected permit does not belong to the selected plot organization'
            }), 400

    # Only the hash is stored, so the raw token exists solely inside the QR image.
    raw_qr_token = secrets.token_urlsafe(32)

    try:
        b = TimberBatch(
            unique_tag_id=tag_id,
            species=normalized_species,
            volume_m3=volume_m3,
            weight_kg=weight_kg,
            harvest_date=harvest_date,
            plot_id=plot.id,
            permit_id=permit.id if permit else None,
            current_status='harvested',
            current_holder_org_id=plot.org_id,
            source_org_id=plot.org_id,
            created_by_user_id=user.id,
            qr_token_hash=_hash_token(raw_qr_token),
            qr_issued_at=datetime.utcnow(),
        )
        db.session.add(b)
        db.session.flush()

        qr_data = generate_qr_code(b.unique_tag_id, raw_qr_token)
        b.qr_code_path = qr_data['path']
        b.qr_code_data = qr_data['base64']

        tx = Transaction(
            batch_id=b.id,
            event_type='harvest',
            initiated_by_user_id=user.id,
            from_user_id=user.id,
            to_user_id=user.id,
            from_org_id=plot.org_id,
            to_org_id=plot.org_id,
            permit_id=permit.id if permit else None,
            quantity_m3=volume_m3,
            weight_kg=weight_kg,
            occurred_at=datetime.utcnow(),
            location_lat=plot.location_lat,
            location_lon=plot.location_lon,
        )
        db.session.add(tx)
        db.session.flush()

        # Hash the values actually stored by MySQL.
        db.session.refresh(tx)

        tx.transaction_hash = hash_transaction(tx)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'The batch could not be saved because of a database constraint'}), 400

    anchor_pending([tx.id])

    log_audit(user.id, 'create_batch', 'timber_batches', b.id, request.remote_addr)
    return jsonify({
        'message': 'Timber batch created successfully',
        'id': b.id,
        'unique_tag_id': b.unique_tag_id,
        'batch': {
            'id': b.id,
            'unique_tag_id': b.unique_tag_id,
            'species': b.species,
            'current_status': b.current_status,
            'plot_id': b.plot_id,
            'permit_id': b.permit_id,
            'current_holder_org_id': b.current_holder_org_id,
        },
        'harvest_transaction_id': tx.id,
        'qr_code': qr_data['base64'],
        'scan_url': qr_data['scan_url'],
        'qr_code_url': url_for('batches.get_qr_code', batch_id=b.id, _external=True),
        'qr_data_url': url_for('batches.get_qr_code_data', batch_id=b.id, _external=True),
        'verify_url': url_for('batches.verify_batch', batch_id=b.id, _external=True)
    }), 201


@batches_bp.route('/batches/<int:batch_id>/qr', methods=['GET'])
@role_required('admin', 'forestry_officer', 'transporter', 'mill')
def get_qr_code(batch_id):
    batch, error = can_access_batch(get_current_user(), batch_id)
    if error:
        return error

    if not batch.qr_code_data:
        _issue_qr(batch)

    full_path = os.path.join(current_app.root_path, batch.qr_code_path)
    if not os.path.exists(full_path):
        _issue_qr(batch)
        full_path = os.path.join(current_app.root_path, batch.qr_code_path)

    return send_file(
        full_path,
        mimetype='image/png',
        as_attachment=False,
        download_name=f'batch_{batch.unique_tag_id}_qr.png'
    )


@batches_bp.route('/batches/<int:batch_id>/qr-data', methods=['GET'])
@role_required('admin', 'forestry_officer', 'transporter', 'mill')
def get_qr_code_data(batch_id):
    batch, error = can_access_batch(get_current_user(), batch_id)
    if error:
        return error

    if not batch.qr_code_data:
        _issue_qr(batch)

    return jsonify({
        'batch_id': batch.id,
        'unique_tag_id': batch.unique_tag_id,
        'qr_code': batch.qr_code_data,
        'qr_base64': f"data:image/png;base64,{batch.qr_code_data}",
        'qr_issued_at': batch.qr_issued_at.isoformat() if batch.qr_issued_at else None,
        'download_url': url_for('batches.download_qr_code', batch_id=batch.id, _external=True),
    })


@batches_bp.route('/batches/<int:batch_id>/qr/rotate', methods=['POST'])
@role_required('admin', 'forestry_officer')
def rotate_qr_code(batch_id):
    batch, error = can_access_batch(get_current_user(), batch_id)
    if error:
        return error

    qr_data = _issue_qr(batch)
    log_audit(get_current_user().id, 'rotate_qr', 'timber_batches', batch.id, request.remote_addr)
    return jsonify({
        'message': 'A new QR token was issued; previously printed labels no longer resolve',
        'batch_id': batch.id,
        'qr_code': qr_data['base64'],
        'scan_url': qr_data['scan_url'],
    })


@batches_bp.route('/batches/<int:batch_id>/qr/revoke', methods=['POST'])
@role_required('admin', 'forestry_officer')
def revoke_qr_code(batch_id):
    batch, error = can_access_batch(get_current_user(), batch_id)
    if error:
        return error

    batch.qr_revoked_at = datetime.utcnow()
    db.session.commit()
    log_audit(get_current_user().id, 'revoke_qr', 'timber_batches', batch.id, request.remote_addr)
    return jsonify({'message': 'QR token revoked', 'batch_id': batch.id})


@batches_bp.route('/batches/<int:batch_id>/qr/download', methods=['GET'])
@role_required('admin', 'forestry_officer', 'transporter', 'mill')
def download_qr_code(batch_id):
    batch, error = can_access_batch(get_current_user(), batch_id)
    if error:
        return error

    if not batch.qr_code_path:
        _issue_qr(batch)

    full_path = os.path.join(current_app.root_path, batch.qr_code_path)
    if not os.path.exists(full_path):
        _issue_qr(batch)
        full_path = os.path.join(current_app.root_path, batch.qr_code_path)

    return send_file(
        full_path,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'batch_{batch.unique_tag_id}_qr.png'
    )


@batches_bp.route('/batches/<int:batch_id>/verify', methods=['GET'])
@role_required('admin', 'forestry_officer', 'transporter', 'mill', 'inspector', 'buyer')
def verify_batch(batch_id):
    batch, error = can_access_batch(get_current_user(), batch_id)
    if error:
        return error

    txs = Transaction.query.filter_by(batch_id=batch_id).order_by(Transaction.id.asc()).all()
    return jsonify({
        'verified': True,
        'batch': {
            'id': batch.id,
            'unique_tag_id': batch.unique_tag_id,
            'species': batch.species,
            'volume_m3': batch.volume_m3,
            'current_status': batch.current_status,
            'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
        },
        'transaction_count': len(txs),
        'transactions': [{
            'id': t.id,
            'type': t.event_type,
            'timestamp': t.occurred_at.isoformat() if t.occurred_at else None,
            'initiated_by_user_id': t.initiated_by_user_id,
            'from_user_id': t.from_user_id,
            'to_user_id': t.to_user_id,
            'from_org_id': t.from_org_id,
            'to_org_id': t.to_org_id,
        } for t in txs]
    })


def _hash_token(raw_token):
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def generate_qr_code(unique_tag_id, raw_token):
    """The QR carries only the opaque scan token, never batch business data."""
    scan_url = url_for('scan_page', token=raw_token, _external=True)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(scan_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color='#3D2B1F', back_color='#FAF5ED')

    qr_dir = os.path.join(current_app.root_path, 'static', 'qr_codes')
    os.makedirs(qr_dir, exist_ok=True)

    safe_tag = secure_filename(str(unique_tag_id))
    filename = f'batch_{safe_tag}.png'
    filepath = os.path.join(qr_dir, filename)
    img.save(filepath, 'PNG', optimize=True)

    buffered = BytesIO()
    img.save(buffered, format='PNG', optimize=True)
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    rel_path = os.path.join('static', 'qr_codes', filename)
    return {
        'path': rel_path,
        'base64': img_base64,
        'scan_url': scan_url,
    }


def _issue_qr(batch):
    """Issues a fresh token, so any previously printed label stops resolving."""
    raw_token = secrets.token_urlsafe(32)
    qr_data = generate_qr_code(batch.unique_tag_id, raw_token)

    batch.qr_token_hash = _hash_token(raw_token)
    batch.qr_issued_at = datetime.utcnow()
    batch.qr_revoked_at = None
    batch.qr_code_path = qr_data['path']
    batch.qr_code_data = qr_data['base64']
    db.session.commit()

    return qr_data