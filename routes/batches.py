import base64
import json
import os
from io import BytesIO

import qrcode
from flask import Blueprint, request, jsonify, current_app, url_for, send_file
from models import db, TimberBatch, Transaction
from auth import log_audit, role_required
from blockchain import anchor_pending
from datetime import datetime
from werkzeug.utils import secure_filename

batches_bp = Blueprint('batches', __name__)


def _normalize_species(data):
  species = (data.get('species') or '').strip()
  species_list = data.get('species_list')

  # Accept list, comma-separated string, or fallback species field.
  if isinstance(species_list, str):
    species_candidates = [s.strip() for s in species_list.split(',') if s.strip()]
  elif isinstance(species_list, list):
    species_candidates = [str(s).strip() for s in species_list if str(s).strip()]
  else:
    species_candidates = []

  if species == '__MULTIPLE__' or len(species_candidates) > 1:
    if not species_candidates:
      return None
    return ', '.join(species_candidates)

  if species_candidates:
    return species_candidates[0]

  return species or None

@batches_bp.route('/batches', methods=['GET'])
@role_required('admin', 'logger', 'transporter', 'mill')
def list_batches():
    rows = TimberBatch.query.order_by(TimberBatch.id.desc()).all()
    return jsonify([{
      'id': r.id, 'unique_tag_id': r.unique_tag_id, 'species': r.species,
      'volume_m3': r.volume_m3, 'current_status': r.current_status,
      'qr_code_path': r.qr_code_path,
    'qr_code_url': url_for('batches.get_qr_code', batch_id=r.id, _external=True),
    'qr_data_url': url_for('batches.get_qr_code_data', batch_id=r.id, _external=True)
    } for r in rows])


@batches_bp.route('/batches/by-tag/<string:tag_id>', methods=['GET'])
@role_required('admin', 'logger', 'transporter', 'mill', 'inspector', 'buyer')
def get_batch_by_tag(tag_id):
    """Lookup batch details by unique tag id for authenticated scanning/track flows."""
    batch = TimberBatch.query.filter_by(unique_tag_id=tag_id).first()
    if not batch:
        return jsonify({'error': 'batch not found'}), 404

    return jsonify({
        'id': batch.id,
        'unique_tag_id': batch.unique_tag_id,
        'species': batch.species,
        'volume_m3': batch.volume_m3,
        'weight_kg': batch.weight_kg,
        'current_status': batch.current_status,
        'current_holder_org_id': batch.current_holder_org_id,
        'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
        'qr_code_url': url_for('batches.get_qr_code', batch_id=batch.id, _external=True),
        'qr_data_url': url_for('batches.get_qr_code_data', batch_id=batch.id, _external=True),
    })

@batches_bp.route('/batches', methods=['POST'])
@role_required('admin', 'logger')
def create_batch():
    data = request.get_json() or {}
    normalized_species = _normalize_species(data)
    if not data.get('unique_tag_id') or data.get('volume_m3') in (None, '') or not normalized_species:
        return jsonify({'error': 'missing required fields: unique_tag_id, species, volume_m3'}), 400

    b = TimberBatch(
        unique_tag_id=data['unique_tag_id'],
        species=normalized_species,
        volume_m3=data['volume_m3'],
        weight_kg=data.get('weight_kg'),
        harvest_date=datetime.strptime(data['harvest_date'], '%Y-%m-%d').date() if data.get('harvest_date') else None,
        plot_id=data.get('plot_id'),
        current_holder_org_id=data.get('current_holder_org_id')
    )
    db.session.add(b)
    db.session.flush()

    qr_data = generate_qr_code(b.id, b.unique_tag_id, {
        **data,
        'species': normalized_species,
    })
    b.qr_code_path = qr_data['path']
    b.qr_code_data = qr_data['base64']

    db.session.commit()

    tx = Transaction(
        batch_id=b.id,
        type='harvest',
        from_user_id=data.get('from_user_id'),
        to_user_id=data.get('to_user_id')
    )
    db.session.add(tx)
    db.session.commit()

    anchor_pending([tx.id])

    log_audit(data.get('from_user_id'), 'create_batch', 'timber_batches', b.id, request.remote_addr)
    return jsonify({
        'id': b.id,
        'unique_tag_id': b.unique_tag_id,
        'qr_code': qr_data['base64'],
        'qr_code_url': url_for('batches.get_qr_code', batch_id=b.id, _external=True),
        'qr_data_url': url_for('batches.get_qr_code_data', batch_id=b.id, _external=True),
        'verify_url': url_for('batches.verify_batch', batch_id=b.id, _external=True)
    }), 201


@batches_bp.route('/batches/<int:batch_id>/qr', methods=['GET'])
@role_required('admin', 'logger', 'transporter', 'mill')
def get_qr_code(batch_id):
    batch = TimberBatch.query.get_or_404(batch_id)
    if not batch.qr_code_data:
        qr_data = generate_qr_code(batch.id, batch.unique_tag_id, {
            'species': batch.species,
            'volume_m3': batch.volume_m3,
            'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
            'plot_id': batch.plot_id,
        })
        batch.qr_code_path = qr_data['path']
        batch.qr_code_data = qr_data['base64']
        db.session.commit()

    full_path = os.path.join(current_app.root_path, batch.qr_code_path)
    return send_file(
        full_path,
        mimetype='image/png',
        as_attachment=False,
        download_name=f'batch_{batch.unique_tag_id}_qr.png'
    )


@batches_bp.route('/batches/<int:batch_id>/qr-data', methods=['GET'])
@role_required('admin', 'logger', 'transporter', 'mill')
def get_qr_code_data(batch_id):
    batch = TimberBatch.query.get_or_404(batch_id)
    if not batch.qr_code_data:
        qr_data = generate_qr_code(batch.id, batch.unique_tag_id, {
            'species': batch.species,
            'volume_m3': batch.volume_m3,
            'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
            'plot_id': batch.plot_id,
        })
        batch.qr_code_path = qr_data['path']
        batch.qr_code_data = qr_data['base64']
        db.session.commit()

    return jsonify({
        'batch_id': batch.id,
        'unique_tag_id': batch.unique_tag_id,
        'qr_code': batch.qr_code_data,
        'qr_base64': f"data:image/png;base64,{batch.qr_code_data}",
        'download_url': url_for('batches.download_qr_code', batch_id=batch.id, _external=True),
        'qr_url': url_for('track_page', _external=True) + f"?tag={batch.unique_tag_id}",
    })


@batches_bp.route('/batches/<int:batch_id>/qr/download', methods=['GET'])
@role_required('admin', 'logger', 'transporter', 'mill')
def download_qr_code(batch_id):
    batch = TimberBatch.query.get_or_404(batch_id)
    if not batch.qr_code_path:
        qr_data = generate_qr_code(batch.id, batch.unique_tag_id, {
            'species': batch.species,
            'volume_m3': batch.volume_m3,
            'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
            'plot_id': batch.plot_id,
        })
        batch.qr_code_path = qr_data['path']
        batch.qr_code_data = qr_data['base64']
        db.session.commit()

    full_path = os.path.join(current_app.root_path, batch.qr_code_path)
    if not os.path.exists(full_path):
        qr_data = generate_qr_code(batch.id, batch.unique_tag_id, {
            'species': batch.species,
            'volume_m3': batch.volume_m3,
            'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
            'plot_id': batch.plot_id,
        })
        batch.qr_code_path = qr_data['path']
        batch.qr_code_data = qr_data['base64']
        db.session.commit()
        full_path = os.path.join(current_app.root_path, batch.qr_code_path)

    return send_file(
        full_path,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'batch_{batch.unique_tag_id}_qr.png'
    )


@batches_bp.route('/batches/<int:batch_id>/verify', methods=['GET'])
@role_required('admin', 'logger', 'transporter', 'mill', 'inspector', 'buyer')
def verify_batch(batch_id):
    batch = TimberBatch.query.get_or_404(batch_id)
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
            'type': t.type,
            'timestamp': t.timestamp.isoformat() if t.timestamp else None,
            'from_user_id': t.from_user_id,
            'to_user_id': t.to_user_id,
        } for t in txs]
    })


def generate_qr_code(batch_id, unique_tag_id, data):
    payload = {
        'batch_id': batch_id,
        'unique_tag_id': unique_tag_id,
        'species': data.get('species', ''),
        'volume_m3': data.get('volume_m3', 0),
        'harvest_date': data.get('harvest_date', ''),
        'plot_id': data.get('plot_id', ''),
        'timestamp': datetime.utcnow().isoformat(),
        'verification_url': url_for('batches.verify_batch', batch_id=batch_id, _external=True),
    }
    qr_string = json.dumps(payload)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_string)
    qr.make(fit=True)

    img = qr.make_image(fill_color='#3D2B1F', back_color='#FAF5ED')

    qr_dir = os.path.join(current_app.root_path, 'static', 'qr_codes')
    os.makedirs(qr_dir, exist_ok=True)

    safe_tag = secure_filename(str(unique_tag_id))
    filename = f'batch_{safe_tag}_{batch_id}.png'
    filepath = os.path.join(qr_dir, filename)
    img.save(filepath, 'PNG', optimize=True)

    buffered = BytesIO()
    img.save(buffered, format='PNG', optimize=True)
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    rel_path = os.path.join('static', 'qr_codes', filename)
    return {
        'path': rel_path,
        'base64': img_base64,
    }