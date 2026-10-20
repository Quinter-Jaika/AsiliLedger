"""Authenticated resolution of QR tokens printed on batch labels."""
import hashlib

from flask import Blueprint, jsonify

from auth import role_required
from models import TimberBatch
from permissions import can_access_batch, get_current_user

scan_bp = Blueprint('scan', __name__)



@scan_bp.route('/scan/<string:token>', methods=['GET'])
@role_required('admin', 'forestry_officer', 'transporter', 'mill', 'inspector', 'buyer')
def resolve_qr_token(token):
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    batch = TimberBatch.query.filter_by(qr_token_hash=token_hash).first()

    if not batch or batch.qr_revoked_at is not None:
        return jsonify({'error': 'Invalid, expired, or revoked QR code'}), 404

    user = get_current_user()

    _, error = can_access_batch(
        user,
        batch.id,
        allow_unassigned_load=True
    )

    if error:
        return error

    role = (user.role or '').lower() if user else ''

    if role in {'inspector', 'buyer'}:
        next_page = f'/template/blockchain?tag={batch.unique_tag_id}'
    else:
        next_page = f'/template/track?tag={batch.unique_tag_id}'

    return jsonify({
        'batch_id': batch.id,
        'unique_tag_id': batch.unique_tag_id,
        'current_status': batch.current_status,
        'next_page': next_page,
    })