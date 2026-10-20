import hashlib, json, time
from datetime import datetime
from models import db, BlockchainBlock, BlockchainBlockTransaction, Transaction
from transaction_utils import hash_transaction

class Block:
    def __init__(self, number, timestamp, prev_hash, tx_hashes, nonce=0):
        self.number = number
        self.timestamp = timestamp
        self.previous_hash = prev_hash
        self.transactions_hash = self._tx_hashes_hash(tx_hashes)
        self.nonce = nonce
        self.block_hash = self._compute_hash()

    def _tx_hashes_hash(self, tx_hashes):
        ordered = json.dumps(sorted(tx_hashes), separators=(',', ':'))
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
        block = blk.to_dict()
        self.chain.append(block)
        return block

    def latest_block_hash(self):
        return self.chain[-1]['block_hash']

chain = Blockchain()
_pending = []
ANCHOR_THRESHOLD = 5


def pending_ids():
    return tuple(_pending)


def reset_chain_state():
    global _pending
    chain.chain = [chain._genesis()]
    _pending = []


def initialize_chain():
    """Restore blocks from the database, creating and persisting genesis once."""
    global _pending
    rows = BlockchainBlock.query.order_by(BlockchainBlock.number.asc()).all()
    if not rows:
        genesis = chain.chain[0]
        db.session.add(BlockchainBlock(
            number=genesis['number'],
            timestamp=datetime.fromtimestamp(genesis['timestamp']),
            previous_hash=genesis['previous_hash'],
            transactions_hash=genesis['transactions_hash'],
            nonce=genesis['nonce'],
            block_hash=genesis['block_hash'],
            metadata_json='{"anchored_via":"genesis"}',
        ))
        db.session.commit()
    else:
        chain.chain = [{
            'number': row.number,
            'timestamp': row.timestamp.timestamp(),
            'previous_hash': row.previous_hash,
            'transactions_hash': row.transactions_hash,
            'nonce': row.nonce,
            'block_hash': row.block_hash,
        } for row in rows]
    anchored_ids = db.session.query(BlockchainBlockTransaction.transaction_id).distinct()
    _pending = [tx_id for (tx_id,) in db.session.query(Transaction.id).filter(
        Transaction.anchored_at.is_(None),
        ~Transaction.id.in_(anchored_ids),
    ).order_by(Transaction.id.asc()).all()]

def anchor_pending(tx_ids=None, force=False):
    """Anchor pending transactions, restoring local state on write failure."""
    global _pending

    if tx_ids is not None:
        for tx_id in tx_ids:
            if tx_id not in _pending:
                _pending.append(tx_id)

    if not _pending:
        return None

    if len(_pending) < ANCHOR_THRESHOLD and not force:
        return None

    pending_snapshot = tuple(_pending)
    original_chain_length = len(chain.chain)

    try:
        transactions = (
            Transaction.query
            .filter(Transaction.id.in_(pending_snapshot))
            .order_by(Transaction.id.asc())
            .all()
        )

        if len(transactions) != len(pending_snapshot):
            raise ValueError(
                "Pending anchor contains an unknown transaction ID"
            )

        for tx in transactions:
            existing_membership = (
                BlockchainBlockTransaction.query
                .filter_by(transaction_id=tx.id)
                .first()
            )

            if tx.anchored_at is not None or existing_membership is not None:
                raise ValueError(
                    f"Transaction {tx.id} is already anchored "
                    "or has an inconsistent anchoring state"
                )

            calculated_hash = hash_transaction(tx)

            # Do not silently replace a conflicting stored hash.
            if (
                tx.transaction_hash
                and tx.transaction_hash != calculated_hash
            ):
                raise ValueError(
                    f"Transaction {tx.id} data does not match "
                    "its stored hash; anchoring stopped"
                )

            if not tx.transaction_hash:
                tx.transaction_hash = calculated_hash

        block = chain.add_block([
            tx.transaction_hash
            for tx in transactions
        ])

        record = BlockchainBlock(
            number=block["number"],
            timestamp=datetime.fromtimestamp(block["timestamp"]),
            previous_hash=block["previous_hash"],
            transactions_hash=block["transactions_hash"],
            nonce=block["nonce"],
            block_hash=block["block_hash"],
            metadata_json='{"anchored_via":"anchor_pending"}',
        )

        db.session.add(record)
        db.session.flush()

        for tx in transactions:
            db.session.add(
                BlockchainBlockTransaction(
                    block_number=block["number"],
                    transaction_id=tx.id,
                    transaction_hash=tx.transaction_hash,
                )
            )

            tx.anchored_at = datetime.utcnow()

        db.session.commit()

    except Exception:
        db.session.rollback()

        # Remove any block appended during this failed attempt.
        del chain.chain[original_chain_length:]

        # Keep pending IDs so the failed work is not silently lost.
        raise

    anchored_ids = set(pending_snapshot)
    _pending = [
        tx_id for tx_id in _pending
        if tx_id not in anchored_ids
    ]

    return block

def verify_chain():
    """
    Verify the persisted database ledger.

    Returns a JSON-serializable dict:
      {"valid": True, ...}
    or
      {"valid": False, "error": "...", ...}
    """
    blocks = (
        BlockchainBlock.query
        .order_by(BlockchainBlock.number.asc())
        .all()
    )

    if not blocks:
        return {
            "valid": False,
            "error": "No blocks found. Initialize the ledger first.",
            "blocks_checked": 0,
            "transactions_checked": 0,
        }

    if blocks[0].number != 0:
        return {
            "valid": False,
            "error": "Genesis block is missing or does not have block number 0.",
            "blocks_checked": 0,
            "transactions_checked": 0,
        }

    transactions_checked = 0

    for index, block in enumerate(blocks):
        if block.number != index:
            return {
                "valid": False,
                "error": f"Unexpected block number {block.number}; expected {index}.",
                "failed_block": block.number,
                "blocks_checked": index,
                "transactions_checked": transactions_checked,
            }

        memberships = (
            BlockchainBlockTransaction.query
            .filter_by(block_number=block.number)
            .order_by(BlockchainBlockTransaction.transaction_id.asc())
            .all()
        )

        stored_hashes = [
            membership.transaction_hash
            for membership in memberships
        ]

        # Confirm each membership agrees with the transaction row and
        # that the transaction still hashes to the expected value.
        for membership in memberships:
            tx = db.session.get(Transaction, membership.transaction_id)

            if tx is None:
                return {
                    "valid": False,
                    "error": (
                        f"Block {block.number} references missing transaction "
                        f"{membership.transaction_id}."
                    ),
                    "failed_block": block.number,
                    "transactions_checked": transactions_checked,
                }

            if not tx.transaction_hash:
                return {
                    "valid": False,
                    "error": (
                        f"Transaction {tx.id} has no stored transaction hash."
                    ),
                    "failed_block": block.number,
                    "failed_transaction": tx.id,
                    "transactions_checked": transactions_checked,
                }

            if membership.transaction_hash != tx.transaction_hash:
                return {
                    "valid": False,
                    "error": (
                        f"Transaction hash differs from block membership "
                        f"for transaction {tx.id}."
                    ),
                    "failed_block": block.number,
                    "failed_transaction": tx.id,
                    "transactions_checked": transactions_checked,
                }

            recalculated_tx_hash = hash_transaction(tx)

            if recalculated_tx_hash != tx.transaction_hash:
                return {
                    "valid": False,
                    "error": (
                        f"Stored transaction data was changed for transaction "
                        f"{tx.id}."
                    ),
                    "failed_block": block.number,
                    "failed_transaction": tx.id,
                    "transactions_checked": transactions_checked,
                }

            transactions_checked += 1

        calculated_transactions_hash = Block(
            number=block.number,
            timestamp=0,
            prev_hash=block.previous_hash,
            tx_hashes=stored_hashes,
            nonce=block.nonce,
        ).transactions_hash

        if calculated_transactions_hash != block.transactions_hash:
            return {
                "valid": False,
                "error": (
                    f"Transaction-list hash does not match block "
                    f"{block.number}."
                ),
                "failed_block": block.number,
                "transactions_checked": transactions_checked,
            }

        if index == 0:
            # This matches the genesis construction in your current code.
            expected_genesis = Block(
                number=0,
                timestamp=0,
                prev_hash="0",
                tx_hashes=[],
                nonce=block.nonce,
            )

            if block.previous_hash != "0":
                return {
                    "valid": False,
                    "error": "Genesis block has an invalid previous_hash.",
                    "failed_block": 0,
                    "transactions_checked": transactions_checked,
                }

            if block.transactions_hash != expected_genesis.transactions_hash:
                return {
                    "valid": False,
                    "error": "Genesis block has an invalid transactions_hash.",
                    "failed_block": 0,
                    "transactions_checked": transactions_checked,
                }

            expected_block_hash = hashlib.sha256(
                (
                    block.previous_hash
                    + block.transactions_hash
                    + str(block.nonce)
                ).encode("utf-8")
            ).hexdigest()

        else:
            previous_block = blocks[index - 1]

            if block.previous_hash != previous_block.block_hash:
                return {
                    "valid": False,
                    "error": (
                        f"Block {block.number} does not link to the "
                        f"previous block."
                    ),
                    "failed_block": block.number,
                    "transactions_checked": transactions_checked,
                }

            expected_block_hash = hashlib.sha256(
                (
                    block.previous_hash
                    + block.transactions_hash
                    + str(block.nonce)
                ).encode("utf-8")
            ).hexdigest()

        if block.block_hash != expected_block_hash:
            return {
                "valid": False,
                "error": f"Block hash is invalid for block {block.number}.",
                "failed_block": block.number,
                "transactions_checked": transactions_checked,
            }

    unanchored_count = (
        Transaction.query
        .filter(Transaction.anchored_at.is_(None))
        .count()
    )

    return {
        "valid": True,
        "blocks_checked": len(blocks),
        "transactions_checked": transactions_checked,
        "unanchored_transactions": unanchored_count,
        "latest_block_number": blocks[-1].number,
        "latest_block_hash": blocks[-1].block_hash,
        "message": "All stored blocks and their transaction memberships are valid.",
    }