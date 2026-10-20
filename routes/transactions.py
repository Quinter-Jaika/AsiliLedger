import math

from flask import Blueprint, request, jsonify
from models import db, Transaction, TimberBatch, Organization
from auth import log_audit, role_required, current_user_id  # adjust to your actual function name if different
from blockchain import anchor_pending  # see fix in blockchain.py below
from datetime import datetime
from permissions import can_access_batch, can_access_vehicle, get_current_user
from sqlalchemy.exc import IntegrityError
from transaction_utils import hash_transaction

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/transactions', methods=['GET'])
@role_required('admin', 'transporter', 'mill', 'inspector', 'buyer')
def list_transactions():
    batch_id = request.args.get('batch_id')
    if batch_id:
        try:
            batch_id = int(batch_id)
        except ValueError:
            return jsonify({'error': 'Invalid batch ID'}), 400
        batch, error = can_access_batch(get_current_user(), batch_id)
        if error:
            return error
        rows = Transaction.query.filter_by(batch_id=batch.id).order_by(Transaction.occurred_at.asc()).all()
    else:
        user = get_current_user()
        query = Transaction.query
        if (user.role or '').lower() != 'admin':
            query = query.join(TimberBatch).filter(
                (TimberBatch.current_holder_org_id == user.org_id)
                | (TimberBatch.source_org_id == user.org_id)
                | (TimberBatch.created_by_user_id == user.id)
            )
        rows = query.order_by(Transaction.occurred_at.desc()).limit(50).all()
    return jsonify([{
        'id': r.id, 'batch_id': r.batch_id,
        'type': r.event_type,
        'status': r.event_status,
        'initiated_by_user_id': r.initiated_by_user_id,
        'from_user_id': r.from_user_id, 'to_user_id': r.to_user_id,
        'from_org_id': r.from_org_id, 'to_org_id': r.to_org_id,
        'vehicle_id': r.vehicle_id, 'permit_id': r.permit_id,
        'timestamp': r.occurred_at.isoformat() if r.occurred_at else None,
        'location_lat': r.location_lat, 'location_lon': r.location_lon,
        'notes': r.notes
    } for r in rows])

@transactions_bp.route('/transactions', methods=['POST'])
@role_required('admin', 'transporter', 'mill')
def create_transaction():
    data = request.get_json() or {}
    event_type = data.get('type')
    if not data.get('batch_id') or not event_type:
        return jsonify({'error': 'missing required fields: batch_id, type'}), 400

    if event_type not in {'load', 'unload', 'process', 'sale'}:
        return jsonify({'error': 'Unsupported transaction type'}), 400

    try:
        batch_id = int(data['batch_id'])
        destination_id = int(data['to_org_id']) if data.get('to_org_id') not in (None, '') else None
        vehicle_id = int(data['vehicle_id']) if data.get('vehicle_id') not in (None, '') else None
        location_lat = float(data['location_lat']) if data.get('location_lat') not in (None, '') else None
        location_lon = float(data['location_lon']) if data.get('location_lon') not in (None, '') else None
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid batch, organization, or vehicle ID'}), 400

    if (location_lat is not None and not math.isfinite(location_lat)) or (
        location_lon is not None and not math.isfinite(location_lon)
    ):
        return jsonify({'error': 'Location coordinates must be finite numbers'}), 400
    if data.get('notes') is not None and (
        not isinstance(data['notes'], str) or len(data['notes']) > 500
    ):
        return jsonify({'error': 'Notes must be text of at most 500 characters'}), 400

    user = get_current_user()
    batch, error = can_access_batch(user, batch_id, allow_unassigned_load=event_type == 'load')
    if error:
        return error

    transitions = {
        'load': ('harvested', 'in_transit', {'transporter'}, None),
        'unload': ('in_transit', 'at_destination', {'transporter'}, 'mill'),
        'process': ('at_destination', 'at_mill', {'mill'}, 'mill'),
        'sale': ('at_mill', 'sold', {'mill'}, 'buyer'),
    }
    required_status, next_status, allowed_roles, destination_type = transitions[event_type]
    role = (user.role or '').lower()
    if role != 'admin' and role not in allowed_roles:
        return jsonify({'error': f'{role} is not authorized to record {event_type} events'}), 403
    if batch.current_status != required_status:
        return jsonify({
            'error': f'Cannot record {event_type} while batch status is {batch.current_status}',
            'required_status': required_status,
        }), 400

    destination = db.session.get(Organization, destination_id) if destination_id else None
    if destination_id is not None and destination is None:
        return jsonify({'error': 'Destination organization not found'}), 404

    if event_type == 'load':
        destination_id = destination_id or (user.org_id if role != 'admin' else None)
        if destination_id is None:
            return jsonify({'error': 'A destination organization is required'}), 400
        if role != 'admin' and destination_id != user.org_id:
            return jsonify({'error': 'A transporter may only load custody into their own organization'}), 403
    elif role != 'admin' and event_type in {'unload', 'process', 'sale'}:
        if batch.current_holder_org_id != user.org_id:
            return jsonify({'error': 'Your organization is not the current batch holder'}), 403
    if event_type == 'process':
        destination_id = destination_id or batch.current_holder_org_id
        if destination_id != batch.current_holder_org_id:
            return jsonify({'error': 'Processing must remain with the current holder organization'}), 400
    elif event_type in {'unload', 'sale'} and destination_id is None:
        return jsonify({'error': 'A destination organization is required'}), 400

    if destination_type and destination and destination.type.lower() != destination_type:
        return jsonify({'error': f'{event_type} destination must be a {destination_type} organization'}), 400

    vehicle = None
    if event_type in {'load', 'unload'} and vehicle_id is None:
        return jsonify({'error': 'A vehicle is required for load and unload events'}), 400
    if vehicle_id is not None:
        vehicle, vehicle_error = can_access_vehicle(user, vehicle_id)
        if vehicle_error:
            return vehicle_error
        if vehicle.capacity_m3 is not None and batch.volume_m3 > vehicle.capacity_m3:
            return jsonify({'error': 'Batch volume exceeds vehicle capacity'}), 400
        if event_type not in {'load', 'unload'}:
            return jsonify({'error': 'Vehicles can only be assigned to load or unload events'}), 400

    previous_event = Transaction.query.filter_by(batch_id=batch.id).order_by(
        Transaction.occurred_at.desc(), Transaction.id.desc()
    ).first()
    from_user_id = previous_event.to_user_id if previous_event and previous_event.to_user_id else user.id
    tx = Transaction(
        batch_id=batch.id,
        event_type=event_type,
        initiated_by_user_id=user.id,
        from_user_id=from_user_id,
        to_user_id=user.id,
        from_org_id=batch.current_holder_org_id,
        to_org_id=destination_id or batch.current_holder_org_id,
        vehicle_id=vehicle.id if vehicle else None,
        location_lat=location_lat,
        location_lon=location_lon,
        notes=data.get('notes'),
    )
    batch.current_status = next_status
    if event_type in {'load', 'unload', 'sale'} and destination_id:
        batch.current_holder_org_id = destination_id
    db.session.add(tx)

    try:
        db.session.flush()

        # Reload values as stored by the database before hashing.
        db.session.refresh(tx)

        tx.transaction_hash = hash_transaction(tx)

        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": (
                "Transaction could not be saved because of "
                "a database constraint"
            )
        }), 400

    except Exception:
        db.session.rollback()
        raise

    # Anchor to blockchain (batch pending txs, then anchor if threshold reached)
    anchor_pending([tx.id])

    log_audit(user.id, 'create_transaction', 'transactions', tx.id, request.remote_addr)
    return jsonify({'id': tx.id, 'batch_id': tx.batch_id, 'type': tx.event_type}), 201

@transactions_bp.route('/transactions/<int:tx_id>', methods=['GET'])
@role_required('admin', 'transporter', 'mill', 'inspector', 'buyer')
def get_transaction(tx_id):
    tx = db.session.get(Transaction, tx_id)
    if not tx:
        return jsonify({'error': 'transaction not found'}), 404
    _, error = can_access_batch(get_current_user(), tx.batch_id)
    if error:
        return error
    return jsonify({
        'id': tx.id, 'batch_id': tx.batch_id,
        'type': tx.event_type,
        'status': tx.event_status,
        'initiated_by_user_id': tx.initiated_by_user_id,
        'from_user_id': tx.from_user_id, 'to_user_id': tx.to_user_id,
        'from_org_id': tx.from_org_id, 'to_org_id': tx.to_org_id,
        'vehicle_id': tx.vehicle_id, 'permit_id': tx.permit_id,
        'timestamp': tx.occurred_at.isoformat() if tx.occurred_at else None,
        'location_lat': tx.location_lat, 'location_lon': tx.location_lon,
        'notes': tx.notes
    })