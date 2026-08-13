import hashlib
from flask import Blueprint, request, jsonify
from datetime import datetime
from models import db, BlockchainBlock
from blockchain import chain, anchor_pending
from auth import role_required

blockchain_bp = Blueprint('blockchain', __name__)

@blockchain_bp.route('/blockchain/latest', methods=['GET'])
@role_required('admin', 'inspector', 'mill', 'buyer')
def get_latest_block():
    """Return the latest block from the blockchain"""
    if chain.chain:
        latest = chain.chain[-1]
        return jsonify({
            'block_number': latest['number'],
            'timestamp': latest['timestamp'],
            'previous_hash': latest['previous_hash'],
            'transactions_hash': latest['transactions_hash'],
            'nonce': latest['nonce'],
            'block_hash': latest['block_hash']
        })
    return jsonify({'error': 'no blocks yet'}), 404

@blockchain_bp.route('/blockchain/block/<int:block_number>', methods=['GET'])
@role_required('admin', 'inspector', 'mill', 'buyer')
def get_block(block_number):
    """Return a specific block by number"""
    for blk in chain.chain:
        if blk['number'] == block_number:
            return jsonify({
                'block_number': blk['number'],
                'timestamp': blk['timestamp'],
                'previous_hash': blk['previous_hash'],
                'transactions_hash': blk['transactions_hash'],
                'nonce': blk['nonce'],
                'block_hash': blk['block_hash']
            })
    return jsonify({'error': 'block not found'}), 404

@blockchain_bp.route('/blockchain/chain', methods=['GET'])
@role_required('admin', 'inspector', 'mill', 'buyer')
def get_chain():
    """Return the entire blockchain (for debugging/verification)"""
    return jsonify([{
        'block_number': blk['number'],
        'timestamp': blk['timestamp'],
        'previous_hash': blk['previous_hash'],
        'transactions_hash': blk['transactions_hash'],
        'nonce': blk['nonce'],
        'block_hash': blk['block_hash']
    } for blk in chain.chain])

@blockchain_bp.route('/blockchain/verify', methods=['GET'])
@role_required('admin', 'inspector', 'mill', 'buyer')
def verify_chain():
    """Verify the blockchain integrity (SHA-256 hash chain)"""
    for i in range(1, len(chain.chain)):
        current = chain.chain[i]
        prev = chain.chain[i-1]

        # Verify previous_hash link
        if current['previous_hash'] != prev['block_hash']:
            return jsonify({'valid': False, 'error': f'Block {i} has invalid previous_hash link'})

        # Verify block_hash computation
        expected_hash = hashlib.sha256(
            (prev['block_hash'] + current['transactions_hash'] + str(current['nonce'])).encode()
        ).hexdigest()
        if current['block_hash'] != expected_hash:
            return jsonify({'valid': False, 'error': f'Block {i} has invalid block_hash'})

    return jsonify({'valid': True, 'total_blocks': len(chain.chain)})

@blockchain_bp.route('/blockchain/anchor', methods=['POST'])
@role_required('admin')
def force_anchor():
    """Force anchor pending transactions to blockchain (for testing)"""
    # anchor_pending will use current pending list; we pass empty to force what's pending
    before = len(anchor_pending.pending)
    if before == 0:
        return jsonify({'message': 'no pending transactions to anchor'}), 400

    # anchor_pending internally creates a block and persists it to DB
    anchor_pending([])  # triggers anchoring of current pending

    after = len(anchor_pending.pending)
    latest = chain.chain[-1]
    return jsonify({
        'anchored': True,
        'block_number': latest['number'],
        'block_hash': latest['block_hash'],
        'transactions_anchored': before - after
    })