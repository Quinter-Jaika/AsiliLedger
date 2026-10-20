import pytest

from blockchain import anchor_pending, initialize_chain, pending_ids
from models import BlockchainBlock, BlockchainBlockTransaction, Transaction, db


def _create_batch(client, auth, new_batch):
    response = client.post('/api/batches', headers=auth('fo_a'), json=new_batch())
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def test_genesis_is_persisted_and_chain_verifies(client, auth, app):
    response = client.get('/api/blockchain/verify', headers=auth('admin'))
    assert response.status_code == 200
    assert response.get_json()['valid'] is True

    with app.app_context():
        genesis = db.session.get(BlockchainBlock, 0)
        assert genesis is not None
        assert genesis.previous_hash == '0'
        assert len(genesis.block_hash) == 64


def test_unanchored_transactions_are_restored_after_chain_reload(client, auth, new_batch, app):
    created = _create_batch(client, auth, new_batch)
    assert created['harvest_transaction_id'] in pending_ids()

    with app.app_context():
        initialize_chain()
        assert created['harvest_transaction_id'] in pending_ids()

    response = client.post('/api/blockchain/anchor', headers=auth('admin'))
    assert response.status_code == 200
    assert response.get_json()['transactions_anchored'] == 1


def test_force_anchor_records_membership_and_hashes(client, auth, new_batch, app):
    created = _create_batch(client, auth, new_batch)
    response = client.post('/api/blockchain/anchor', headers=auth('admin'))
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['transactions_anchored'] == 1

    with app.app_context():
        member = BlockchainBlockTransaction.query.one()
        tx = db.session.get(Transaction, member.transaction_id)
        assert member.block_number == response.get_json()['block_number']
        assert member.transaction_hash == tx.transaction_hash
        assert tx.anchored_at is not None

    block = client.get(
        f"/api/blockchain/block/{response.get_json()['block_number']}",
        headers=auth('admin'),
    )
    assert block.status_code == 200
    assert block.get_json()['transaction_ids'] == [created['harvest_transaction_id']]


def test_only_admin_can_force_anchor(client, auth, new_batch):
    _create_batch(client, auth, new_batch)
    response = client.post('/api/blockchain/anchor', headers=auth('transporter'))
    assert response.status_code == 403


@pytest.mark.parametrize('tamper_field', ['previous_hash', 'transactions_hash', 'block_hash'])
def test_block_tampering_is_reported(client, auth, new_batch, app, tamper_field):
    _create_batch(client, auth, new_batch)
    anchored = client.post('/api/blockchain/anchor', headers=auth('admin'))
    assert anchored.status_code == 200

    with app.app_context():
        block = db.session.get(BlockchainBlock, anchored.get_json()['block_number'])
        setattr(block, tamper_field, 'f' * 64)
        db.session.commit()

    response = client.get('/api/blockchain/verify', headers=auth('admin'))
    assert response.status_code == 200
    assert response.get_json()['valid'] is False


def test_transaction_data_tampering_is_reported(client, auth, new_batch, app):
    created = _create_batch(client, auth, new_batch)
    client.post('/api/blockchain/anchor', headers=auth('admin'))

    with app.app_context():
        tx = db.session.get(Transaction, created['harvest_transaction_id'])
        tx.notes = 'silently modified'
        db.session.commit()

    response = client.get('/api/blockchain/verify', headers=auth('admin'))
    assert response.get_json()['valid'] is False


def test_threshold_anchor_creates_block_with_five_members(client, auth, new_batch, app, fixtures):
    created = _create_batch(client, auth, new_batch)
    batch_id = created['id']
    transitions = [
        ('load', 'transporter', fixtures['orgs']['transporter'], fixtures['vehicles']['transporter']),
        ('unload', 'transporter', fixtures['orgs']['mill'], fixtures['vehicles']['transporter']),
        ('process', 'mill', fixtures['orgs']['mill'], None),
        ('sale', 'mill', fixtures['orgs']['buyer'], None),
    ]
    for event_type, role, org_id, vehicle_id in transitions:
        headers = auth(role)
        payload = {'batch_id': batch_id, 'type': event_type, 'to_org_id': org_id}
        if vehicle_id:
            payload['vehicle_id'] = vehicle_id
        response = client.post('/api/transactions', headers=headers, json=payload)
        assert response.status_code == 201, response.get_json()

    with app.app_context():
        block = BlockchainBlock.query.filter(BlockchainBlock.number > 0).one()
        members = BlockchainBlockTransaction.query.filter_by(block_number=block.number).all()
        assert len(members) == 5
        assert not pending_ids()

    assert client.get('/api/blockchain/verify', headers=auth('admin')).get_json()['valid'] is True


def test_transactions_list_is_chronological(client, auth, new_batch, fixtures):
    created = _create_batch(client, auth, new_batch)
    batch_id = created['id']
    for event_type, org_id, vehicle_id in [
        ('load', fixtures['orgs']['transporter'], fixtures['vehicles']['transporter']),
        ('unload', fixtures['orgs']['mill'], fixtures['vehicles']['transporter']),
    ]:
        response = client.post('/api/transactions', headers=auth('transporter'), json={
            'batch_id': batch_id,
            'type': event_type,
            'to_org_id': org_id,
            'vehicle_id': vehicle_id,
        })
        assert response.status_code == 201

    response = client.get(f'/api/transactions?batch_id={batch_id}', headers=auth('transporter'))
    assert response.status_code == 200
    rows = response.get_json()
    assert [row['type'] for row in rows] == ['harvest', 'load', 'unload']
    assert [row['timestamp'] for row in rows] == sorted(row['timestamp'] for row in rows)


def test_lookup_shows_one_pending_transaction_and_custody_neighbors(client, auth, new_batch, fixtures):
    created = _create_batch(client, auth, new_batch)
    batch_id = created['id']
    loaded = client.post('/api/transactions', headers=auth('transporter'), json={
        'batch_id': batch_id,
        'type': 'load',
        'to_org_id': fixtures['orgs']['transporter'],
        'vehicle_id': fixtures['vehicles']['transporter'],
    })
    assert loaded.status_code == 201

    response = client.get(
        f"/api/blockchain/transaction/{created['harvest_transaction_id']}",
        headers=auth('fo_a'),
    )
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result['transaction']['type'] == 'harvest'
    assert result['transaction']['custody_position'] == 1
    assert result['transaction']['custody_event_count'] == 2
    assert result['transaction']['next_event_id'] == loaded.get_json()['id']
    assert result['transaction']['hash_valid'] is True
    assert result['anchor']['anchored'] is False
    assert result['batch']['unique_tag_id'] == created['unique_tag_id']


def test_lookup_by_hash_includes_exact_block_membership(client, auth, new_batch):
    created = _create_batch(client, auth, new_batch)
    anchor = client.post('/api/blockchain/anchor', headers=auth('admin'))
    assert anchor.status_code == 200
    tx_id = created['harvest_transaction_id']

    with client.application.app_context():
        transaction = db.session.get(Transaction, tx_id)
        tx_hash = transaction.transaction_hash

    response = client.get(f'/api/blockchain/transaction/{tx_hash}', headers=auth('admin'))
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result['transaction']['id'] == tx_id
    assert result['anchor']['anchored'] is True
    assert result['anchor']['block_number'] == anchor.get_json()['block_number']
    assert result['anchor']['transaction_hash_matches'] is True
    assert result['transaction']['from_org_name'] == 'Org A Logging'


def test_transaction_chain_lookup_handles_not_found_and_scope(client, auth, new_batch):
    assert client.get('/api/blockchain/transaction/999999', headers=auth('admin')).status_code == 404
    created = _create_batch(client, auth, new_batch)
    response = client.get(
        f"/api/blockchain/transaction/{created['harvest_transaction_id']}",
        headers=auth('fo_b'),
    )
    assert response.status_code == 403


def test_batch_tag_lookup_returns_full_ordered_chain_and_block_membership(client, auth, new_batch, fixtures):
    created = _create_batch(client, auth, new_batch)
    batch_id = created['id']
    loaded = client.post('/api/transactions', headers=auth('transporter'), json={
        'batch_id': batch_id,
        'type': 'load',
        'to_org_id': fixtures['orgs']['transporter'],
        'vehicle_id': fixtures['vehicles']['transporter'],
    })
    assert loaded.status_code == 201
    anchor = client.post('/api/blockchain/anchor', headers=auth('admin'))
    assert anchor.status_code == 200

    response = client.get(
        f"/api/blockchain/batch/{created['unique_tag_id'].lower()}",
        headers=auth('transporter'),
    )
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result['batch']['unique_tag_id'] == created['unique_tag_id']
    assert [event['type'] for event in result['transactions']] == ['harvest', 'load']
    assert [event['position'] for event in result['transactions']] == [1, 2]
    assert all(event['anchored'] and event['membership_matches'] for event in result['transactions'])
    assert result['transactions'][1]['from_org'] == 'Org A Logging'


def test_batch_tag_lookup_is_not_found_and_object_scoped(client, auth, new_batch):
    assert client.get('/api/blockchain/batch/MISSING', headers=auth('admin')).status_code == 404
    created = _create_batch(client, auth, new_batch)
    response = client.get(
        f"/api/blockchain/batch/{created['unique_tag_id']}",
        headers=auth('fo_b'),
    )
    assert response.status_code == 403
