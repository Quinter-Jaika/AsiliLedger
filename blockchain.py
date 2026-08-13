import hashlib, json, time
from datetime import datetime
from models import db, BlockchainBlock

class Block:
    def __init__(self, number, timestamp, prev_hash, tx_hashes, nonce=0):
        self.number = number
        self.timestamp = timestamp
        self.previous_hash = prev_hash
        self.transactions_hash = self._tx_hashes_hash(tx_hashes)
        self.nonce = nonce
        self.block_hash = self._compute_hash()

    def _tx_hashes_hash(self, tx_hashes):
        ordered = json.dumps(sorted(tx_hashes), sort_keys=True)
        return hashlib.sha256(ordered.encode()).hexdigest()

    def _compute_hash(self):
        data = self.previous_hash + self.transactions_hash + str(self.nonce)
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self):
        return {k: getattr(self, k) for k in ['number','timestamp','previous_hash','transactions_hash','nonce','block_hash']}

class Blockchain:
    def __init__(self):
        self.chain = [self._genesis()]

    def _genesis(self):
        return Block(0, time.time(), '0', []).to_dict()

    def add_block(self, tx_hashes):
        prev = self.chain[-1]
        blk = Block(len(self.chain), time.time(), prev['block_hash'], tx_hashes)
        self.chain.append(blk.to_dict())
        return blk

    def latest_block_hash(self):
        return self.chain[-1]['block_hash']

chain = Blockchain()
_pending = []

def anchor_pending(tx_ids=None):
    """Add tx_ids to pending, anchor if >= 5 pending"""
    global _pending
    if tx_ids is not None:
        _pending.extend(tx_ids)
    if len(_pending) >= 5:
        blk = chain.add_block([str(tid) for tid in _pending])
        rec = BlockchainBlock(
            number=blk['number'],
            timestamp=datetime.fromtimestamp(blk['timestamp']),
            previous_hash=blk['previous_hash'],
            transactions_hash=blk['transactions_hash'],
            nonce=blk['nonce'],
            block_hash=blk['block_hash'],
            metadata_json='{"anchored_via":"anchor_pending"}'
        )
        db.session.add(rec)
        db.session.commit()
        _pending.clear()