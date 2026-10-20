from flask import Blueprint, jsonify, request

from auth import role_required
from models import AuditLog

audit_bp = Blueprint('audit', __name__)


@audit_bp.route('/audit-logs', methods=['GET'])
@role_required('admin')
def list_audit_logs():
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return jsonify({'error': 'limit and offset must be integers'}), 400

    if limit < 1 or limit > 500 or offset < 0:
        return jsonify({'error': 'limit must be 1-500 and offset must be non-negative'}), 400

    rows = AuditLog.query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    return jsonify([{
        'id': row.id,
        'user_id': row.user_id,
        'action': row.action,
        'table_affected': row.table_affected,
        'record_id': row.record_id,
        'timestamp': row.timestamp.isoformat() if row.timestamp else None,
        'ip_address': row.ip_address,
    } for row in rows])
