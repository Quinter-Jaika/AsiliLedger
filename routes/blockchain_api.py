import hashlib
import json
from flask import Blueprint, request, jsonify
from datetime import datetime
from models import db, BlockchainBlock, BlockchainBlockTransaction, Transaction, TimberBatch, User, Organization, ForestPlot
from blockchain import chain, anchor_pending, pending_ids, verify_chain
from auth import role_required
from permissions import can_access_batch, get_current_user
from transaction_utils import hash_transaction

blockchain_bp = Blueprint('blockchain', __name__)


@blockchain_bp.route('/blockchain/batch/<string:tag_id>', methods=['GET'])
@role_required('admin', 'forestry_officer', 'transporter', 'mill', 'inspector', 'buyer')
def get_batch_chain(tag_id):
    batch = TimberBatch.query.filter_by(unique_tag_id=tag_id.strip().upper()).first()
    if not batch:
        return jsonify({'error': 'Batch not found'}), 404

    batch, error = can_access_batch(get_current_user(), batch.id)
    if error:
        return error

    events = Transaction.query.filter_by(batch_id=batch.id).order_by(
        Transaction.occurred_at.asc(), Transaction.id.asc()
    ).all()
    timeline = []
    for index, event in enumerate(events):
        actor = db.session.get(User, event.initiated_by_user_id)
        from_org = db.session.get(Organization, event.from_org_id) if event.from_org_id else None
        to_org = db.session.get(Organization, event.to_org_id) if event.to_org_id else None
        membership = BlockchainBlockTransaction.query.filter_by(transaction_id=event.id).first()
        block = db.session.get(BlockchainBlock, membership.block_number) if membership else None

        timeline.append({
            'id': event.id,
            'type': event.event_type,
            'status': event.event_status,
            'occurred_at': event.occurred_at.isoformat() if event.occurred_at else None,
            'actor': actor.name if actor else None,
            'from_org': from_org.name if from_org else None,
            'to_org': to_org.name if to_org else None,
            'quantity_m3': event.quantity_m3,
            'weight_kg': event.weight_kg,
            'location_lat': event.location_lat,
            'location_lon': event.location_lon,
            'hash_valid': bool(
                event.transaction_hash and hash_transaction(event) == event.transaction_hash
            ),
            'position': index + 1,
            'anchored': bool(block),
            'block_number': block.number if block else None,
            'block_hash': block.block_hash if block else None,
            'block_transactions_hash': block.transactions_hash if block else None,
            'membership_matches': bool(
                membership and membership.transaction_hash == event.transaction_hash
            ),
        })

    plot = db.session.get(ForestPlot, batch.plot_id) if batch.plot_id else None
    holder = db.session.get(Organization, batch.current_holder_org_id) if batch.current_holder_org_id else None
    return jsonify({
        'batch': {
            'id': batch.id,
            'unique_tag_id': batch.unique_tag_id,
            'species': batch.species,
            'volume_m3': batch.volume_m3,
            'weight_kg': batch.weight_kg,
            'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
            'current_status': batch.current_status,
            'current_holder': holder.name if holder else None,
            'plot': plot.forest_name if plot else None,
        },
        'transaction_count': len(timeline),
        'transactions': timeline,
    })


@blockchain_bp.route('/blockchain/transaction/<string:transaction_ref>', methods=['GET'])
@role_required('admin', 'forestry_officer', 'transporter', 'mill', 'inspector', 'buyer')
def get_transaction_chain(transaction_ref):
    if transaction_ref.isdigit():
        transaction = db.session.get(Transaction, int(transaction_ref))
    else:
        transaction = Transaction.query.filter_by(transaction_hash=transaction_ref.lower()).first()

    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404

    batch, error = can_access_batch(get_current_user(), transaction.batch_id)
    if error:
        return error

    events = Transaction.query.filter_by(batch_id=batch.id).order_by(
        Transaction.occurred_at.asc(), Transaction.id.asc()
    ).all()
    position = next(index for index, event in enumerate(events) if event.id == transaction.id)

    actor = db.session.get(User, transaction.initiated_by_user_id)
    from_org = db.session.get(Organization, transaction.from_org_id) if transaction.from_org_id else None
    to_org = db.session.get(Organization, transaction.to_org_id) if transaction.to_org_id else None
    block_member = BlockchainBlockTransaction.query.filter_by(
        transaction_id=transaction.id
    ).first()
    block = db.session.get(BlockchainBlock, block_member.block_number) if block_member else None

    return jsonify({
        'transaction': {
            'id': transaction.id,
            'hash': transaction.transaction_hash,
            'hash_valid': bool(
                transaction.transaction_hash
                and hash_transaction(transaction) == transaction.transaction_hash
            ),
            'type': transaction.event_type,
            'status': transaction.event_status,
            'occurred_at': transaction.occurred_at.isoformat() if transaction.occurred_at else None,
            'initiated_by_user_id': transaction.initiated_by_user_id,
            'initiated_by_name': actor.name if actor else None,
            'from_user_id': transaction.from_user_id,
            'to_user_id': transaction.to_user_id,
            'from_org_id': transaction.from_org_id,
            'from_org_name': from_org.name if from_org else None,
            'to_org_id': transaction.to_org_id,
            'to_org_name': to_org.name if to_org else None,
            'vehicle_id': transaction.vehicle_id,
            'permit_id': transaction.permit_id,
            'quantity_m3': transaction.quantity_m3,
            'weight_kg': transaction.weight_kg,
            'location_lat': transaction.location_lat,
            'location_lon': transaction.location_lon,
            'notes': transaction.notes,
            'custody_position': position + 1,
            'custody_event_count': len(events),
            'previous_event_id': events[position - 1].id if position else None,
            'next_event_id': events[position + 1].id if position + 1 < len(events) else None,
        },
        'batch': {
            'id': batch.id,
            'unique_tag_id': batch.unique_tag_id,
            'species': batch.species,
            'current_status': batch.current_status,
        },
        'anchor': {
            'anchored': bool(block),
            'block_number': block.number if block else None,
            'block_timestamp': block.timestamp.isoformat() if block and block.timestamp else None,
            'previous_block_hash': block.previous_hash if block else None,
            'transactions_hash': block.transactions_hash if block else None,
            'block_hash': block.block_hash if block else None,
            'transaction_hash': block_member.transaction_hash if block_member else None,
            'transaction_hash_matches': bool(
                block_member and block_member.transaction_hash == transaction.transaction_hash
            ),
        },
    })

@blockchain_bp.route('/blockchain/latest', methods=['GET'])
@role_required('admin', 'inspector', 'mill', 'buyer')
def get_latest_block():
    """Return the latest block from the blockchain"""
    latest = BlockchainBlock.query.order_by(BlockchainBlock.number.desc()).first()
    if latest:
        return jsonify({
            'block_number': latest.number,
            'timestamp': latest.timestamp.isoformat() if latest.timestamp else None,
            'previous_hash': latest.previous_hash,
            'transactions_hash': latest.transactions_hash,
            'nonce': latest.nonce,
            'block_hash': latest.block_hash
        })
    return jsonify({'error': 'no blocks yet'}), 404

@blockchain_bp.route('/blockchain/block/<int:block_number>', methods=['GET'])
@role_required('admin', 'inspector', 'mill', 'buyer')
def get_block(block_number):
    """Return a specific block by number"""
    block = db.session.get(BlockchainBlock, block_number)
    if not block:
        return jsonify({'error': 'block not found'}), 404
    members = BlockchainBlockTransaction.query.filter_by(block_number=block.number).all()
    return jsonify({
        'block_number': block.number,
        'timestamp': block.timestamp.isoformat() if block.timestamp else None,
        'previous_hash': block.previous_hash,
        'transactions_hash': block.transactions_hash,
        'nonce': block.nonce,
        'block_hash': block.block_hash,
        'transaction_ids': [member.transaction_id for member in members],
        'transaction_hashes': [member.transaction_hash for member in members],
    })

@blockchain_bp.route('/blockchain/chain', methods=['GET'])
@role_required('admin', 'inspector', 'mill', 'buyer')
def get_chain():
    """Return the entire blockchain (for debugging/verification)"""
    return jsonify([{
        'block_number': blk.number,
        'timestamp': blk.timestamp.isoformat() if blk.timestamp else None,
        'previous_hash': blk.previous_hash,
        'transactions_hash': blk.transactions_hash,
        'nonce': blk.nonce,
        'block_hash': blk.block_hash,
        'transaction_ids': [m.transaction_id for m in BlockchainBlockTransaction.query.filter_by(block_number=blk.number).all()],
    } for blk in BlockchainBlock.query.order_by(BlockchainBlock.number.asc()).all()])

@blockchain_bp.route('/blockchain/verify', methods=['GET'])
@role_required('admin', 'inspector', 'mill', 'buyer')
def verify_chain():
    """Verify persisted block links, memberships, and transaction hashes."""

    blocks = (
        BlockchainBlock.query
        .order_by(BlockchainBlock.number.asc())
        .all()
    )

    transactions_checked = 0

    def failure(message, block_number=None, transaction_id=None):
        result = {
            "valid": False,
            "error": message,
            "transactions_checked": transactions_checked,
        }

        if block_number is not None:
            result["failed_block"] = block_number

        if transaction_id is not None:
            result["failed_transaction"] = transaction_id

        response = jsonify(result)
        response.headers["Cache-Control"] = "no-store"
        return response, 409

    if not blocks:
        return failure("No persisted genesis block")

    seen_transaction_ids = set()

    for index, current in enumerate(blocks):
        # 1. Verify sequential block numbering.
        if current.number != index:
            return failure(
                f"Unexpected block number {current.number}; expected {index}.",
                block_number=current.number,
            )

        # 2. Verify the previous-block link.
        expected_previous_hash = (
            "0" if index == 0 else blocks[index - 1].block_hash
        )

        if current.previous_hash != expected_previous_hash:
            return failure(
                f"Block {index} has an invalid previous_hash link.",
                block_number=current.number,
            )

        # 3. Recalculate the block hash using the current hash format.
        expected_block_hash = hashlib.sha256(
            (
                current.previous_hash
                + current.transactions_hash
                + str(current.nonce)
            ).encode("utf-8")
        ).hexdigest()

        if current.block_hash != expected_block_hash:
            return failure(
                f"Block {index} has an invalid block_hash.",
                block_number=current.number,
            )

        members = (
            BlockchainBlockTransaction.query
            .filter_by(block_number=current.number)
            .all()
        )

        # 4. Check genesis or each member transaction.
        if index == 0:
            if members:
                return failure(
                    "Genesis block cannot contain transactions.",
                    block_number=0,
                )

            if current.nonce != 0:
                return failure(
                    "Genesis block must have nonce 0.",
                    block_number=0,
                )

            expected_transactions_hash = hashlib.sha256(
                b"[]"
            ).hexdigest()

        else:
            if not members:
                return failure(
                    f"Block {index} has no transaction membership records.",
                    block_number=current.number,
                )

            hashes = []

            for member in members:
                if member.transaction_id in seen_transaction_ids:
                    return failure(
                        f"Transaction {member.transaction_id} appears "
                        "more than once in the ledger.",
                        block_number=current.number,
                        transaction_id=member.transaction_id,
                    )

                tx = db.session.get(
                    Transaction,
                    member.transaction_id
                )

                if tx is None or not tx.transaction_hash:
                    return failure(
                        f"Block {index} references a missing transaction "
                        "or a transaction without a stored hash.",
                        block_number=current.number,
                        transaction_id=member.transaction_id,
                    )

                if member.transaction_hash != tx.transaction_hash:
                    return failure(
                        f"Transaction {tx.id} does not match its "
                        "block membership hash.",
                        block_number=current.number,
                        transaction_id=tx.id,
                    )

                if hash_transaction(tx) != tx.transaction_hash:
                    return failure(
                        f"Transaction {tx.id} data does not match "
                        "its stored hash.",
                        block_number=current.number,
                        transaction_id=tx.id,
                    )

                if tx.anchored_at is None:
                    return failure(
                        f"Transaction {tx.id} has a block membership "
                        "but no anchoring timestamp.",
                        block_number=current.number,
                        transaction_id=tx.id,
                    )

                seen_transaction_ids.add(tx.id)
                hashes.append(member.transaction_hash)
                transactions_checked += 1

            canonical = json.dumps(
                sorted(hashes),
                separators=(",", ":")
            )

            expected_transactions_hash = hashlib.sha256(
                canonical.encode("utf-8")
            ).hexdigest()

        # 5. Verify the block's aggregate transaction hash.
        if current.transactions_hash != expected_transactions_hash:
            return failure(
                f"Block {index} has an invalid transactions_hash.",
                block_number=current.number,
            )

    # 6. Detect membership rows referencing missing blocks.
    orphan_member = (
        db.session.query(BlockchainBlockTransaction)
        .outerjoin(
            BlockchainBlock,
            BlockchainBlockTransaction.block_number
            == BlockchainBlock.number,
        )
        .filter(BlockchainBlock.number.is_(None))
        .first()
    )

    if orphan_member is not None:
        return failure(
            "A transaction membership references a missing block.",
            block_number=orphan_member.block_number,
            transaction_id=orphan_member.transaction_id,
        )

    # 7. Detect transactions marked anchored but lacking membership.
    membership_exists = (
        db.session.query(BlockchainBlockTransaction)
        .filter(
            BlockchainBlockTransaction.transaction_id
            == Transaction.id
        )
        .exists()
    )

    missing_membership = (
        Transaction.query
        .filter(
            Transaction.anchored_at.isnot(None),
            ~membership_exists,
        )
        .first()
    )

    if missing_membership is not None:
        return failure(
            f"Transaction {missing_membership.id} is marked anchored "
            "but has no block membership.",
            transaction_id=missing_membership.id,
        )

    unanchored_count = (
        Transaction.query
        .filter(Transaction.anchored_at.is_(None))
        .count()
    )

    response = jsonify({
        "valid": True,
        "blocks_checked": len(blocks),
        "transactions_checked": transactions_checked,
        "unanchored_transactions": unanchored_count,
        "latest_block_number": blocks[-1].number,
        "latest_block_hash": blocks[-1].block_hash,
        "message": (
            "All persisted blocks and anchored transaction "
            "memberships passed verification."
        ),
    })

    response.headers["Cache-Control"] = "no-store"
    return response, 200

@blockchain_bp.route('/blockchain/anchor', methods=['POST'])
@role_required('admin')
def force_anchor():
    """Force anchor pending transactions to blockchain (for testing)"""
    before = len(pending_ids())
    if before == 0:
        return jsonify({'message': 'no pending transactions to anchor'}), 400

    block = anchor_pending(force=True)
    return jsonify({
        'anchored': True,
        'block_number': block['number'],
        'block_hash': block['block_hash'],
        'transactions_anchored': before,
    })