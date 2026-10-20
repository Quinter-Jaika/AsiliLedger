def test_new_batch_page_exposes_required_plot_and_permit_dropdowns(client):
    response = client.get('/template/new-batch')
    assert response.status_code == 200
    assert b'id="plot_id" required' in response.data
    assert b'id="permit_id" required' in response.data
    assert b'id="currentOrgName"' in response.data
    assert b'current_holder_org_id' not in response.data
    assert b'from_user_id' not in response.data
    assert b'to_user_id' not in response.data


def test_track_page_has_custody_detail_and_transaction_selects(client):
    response = client.get('/template/track')
    assert response.status_code == 200
    for element_id in (
        b'batchHarvestDate',
        b'batchPlot',
        b'batchHolder',
        b'destinationOrgSelect',
        b'transactionVehicleSelect',
    ):
        assert element_id in response.data


def test_frontend_loads_scoped_reference_data_and_resolves_qr_tokens(client):
    page = client.get('/template/new-batch').get_data(as_text=True)
    assert "'/api/forest-plots'" in page
    assert "'/api/permits?type=harvest'" in page
    assert 'textContent = uniqueTagId' in page

    response = client.get('/static/js/app.js')
    assert response.status_code == 200
    script = response.get_data(as_text=True)
    assert "API + '/scan/'" in script
    assert "get('tag')" in script


def test_blockchain_page_centers_batch_tag_lookup(client):
    response = client.get('/template/blockchain')
    assert response.status_code == 200
    assert b'id="blockchainBatchLookupForm"' in response.data
    assert b'Batch Tag ID' in response.data
    assert b'id="batchChainEvents"' in response.data
    assert b'Full Chain' not in response.data
