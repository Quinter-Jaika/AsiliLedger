from flask import Blueprint, request, jsonify
from models import db, Transaction, TimberBatch
from auth import log_audit, role_required  # adjust to your actual function name if different
from blockchain import anchor_pending  # see fix in blockchain.py below
from datetime import datetime

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/transactions', methods=['GET'])
@role_required('admin', 'transporter', 'mill', 'inspector', 'buyer')
def list_transactions():
    batch_id = request.args.get('batch_id')
    if batch_id:
        rows = Transaction.query.filter_by(batch_id=batch_id).order_by(Transaction.timestamp.asc()).all()
    else:
        rows = Transaction.query.order_by(Transaction.timestamp.desc()).limit(50).all()
    return jsonify([{
        'id': r.id, 'batch_id': r.batch_id,
        'from_user_id': r.from_user_id, 'to_user_id': r.to_user_id,
        'type': r.type,
        'timestamp': r.timestamp.isoformat() if r.timestamp else None,
        'location_lat': r.location_lat, 'location_lon': r.location_lon,
        'document_refs': r.document_refs
    } for r in rows])

@transactions_bp.route('/transactions', methods=['POST'])
@role_required('admin', 'transporter', 'mill')
def create_transaction():
    data = request.get_json()
    batch = TimberBatch.query.get(data['batch_id'])
    if not batch:
        return jsonify({'error': 'batch not found'}), 404

    tx = Transaction(
        batch_id=data['batch_id'],
        from_user_id=data.get('from_user_id'),
        to_user_id=data.get('to_user_id'),
        type=data['type'],  # harvest, load, unload, process, sale
        location_lat=data.get('location_lat'),
        location_lon=data.get('location_lon'),
        document_refs=data.get('document_refs')
    )
    db.session.add(tx)
    db.session.commit()

    # Update batch status based on transaction type
    if data['type'] == 'load':
        batch.current_status = 'in_transit'
    elif data['type'] == 'unload':
        batch.current_status = 'at_destination'
    elif data['type'] == 'process':
        batch.current_status = 'at_mill'
    elif data['type'] == 'sale':
        batch.current_status = 'sold'
    batch.current_holder_org_id = data.get('to_user_id')
    db.session.commit()

    # Anchor to blockchain (batch pending txs, then anchor if threshold reached)
    anchor_pending([tx.id])

    log_audit(tx.from_user_id or tx.to_user_id, 'create_transaction', 'transactions', tx.id, request.remote_addr)
    return jsonify({'id': tx.id, 'batch_id': tx.batch_id, 'type': tx.type}), 201

@transactions_bp.route('/transactions/<int:tx_id>', methods=['GET'])
@role_required('admin', 'transporter', 'mill', 'inspector', 'buyer')
def get_transaction(tx_id):
    tx = Transaction.query.get(tx_id)
    if not tx:
        return jsonify({'error': 'transaction not found'}), 404
    return jsonify({
        'id': tx.id, 'batch_id': tx.batch_id,
        'from_user_id': tx.from_user_id, 'to_user_id': tx.to_user_id,
        'type': tx.type,
        'timestamp': tx.timestamp.isoformat() if tx.timestamp else None,
        'location_lat': tx.location_lat, 'location_lon': tx.location_lon,
        'document_refs': tx.document_refs
    })