const API = '/api';
let token = localStorage.getItem('token');

function decodeJwtPayload(jwtToken){
  try {
    const part = jwtToken.split('.')[1];
    if(!part) return null;
    const base64 = part.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch (_e) {
    return null;
  }
}

function getCurrentRole(){
  const storedRole = localStorage.getItem('role');
  if(storedRole) return storedRole;
  if(!token) return null;

  const payload = decodeJwtPayload(token);
  const role = payload?.role || null;
  if(role) localStorage.setItem('role', role);
  return role;
}

function getCurrentUserId(){
  if(!token) return null;
  const payload = decodeJwtPayload(token);
  return payload?.user_id || null;
}

function formatRole(role){
  const labels = { forestry_officer: 'Forestry Officer' };
  const normalizedRole = (role || '').toLowerCase();
  if(labels[normalizedRole]) return labels[normalizedRole];
  return normalizedRole ? normalizedRole.charAt(0).toUpperCase() + normalizedRole.slice(1) : '-';
}

function getAllowedRoutesForRole(role){
  const normalizedRole = (role || '').toLowerCase();
  const roleNavMap = {
    admin: ['/template/dashboard', '/template/track', '/template/new-batch', '/template/users', '/template/blockchain', '/template/settings'],
    forestry_officer: ['/template/new-batch'],
    transporter: ['/template/track'],
    mill: ['/template/track', '/template/blockchain'],
    inspector: ['/template/blockchain'],
    buyer: ['/template/blockchain']
  };
  return roleNavMap[normalizedRole] || [];
}

function canViewBlockchain(){
  const role = (getCurrentRole() || '').toLowerCase();
  return ['admin', 'inspector', 'mill', 'buyer'].includes(role);
}

function extractTagIdFromScannedText(decodedText){
  const text = (decodedText || '').trim();
  if(!text) return null;

  try {
    const parsed = JSON.parse(text);
    if(parsed?.unique_tag_id) return String(parsed.unique_tag_id).trim();
  } catch (_e) {
    // Not JSON payload.
  }

  try {
    const u = new URL(text);
    const fromQuery = u.searchParams.get('tag');
    if(fromQuery) return fromQuery.trim();

    const pathParts = u.pathname.split('/').filter(Boolean);
    return pathParts[pathParts.length - 1] || null;
  } catch (_e) {
    // Not URL payload.
  }

  return text;
}

function applyRoleBasedNavigation(){
  const role = getCurrentRole();
  if(!role) return;

  const allowedRoutes = getAllowedRoutesForRole(role);
  const navLinks = Array.from(document.querySelectorAll('#sidebar .nav-link[href^="/template/"]'));

  navLinks.forEach(link => {
    const href = link.getAttribute('href');
    const allowed = allowedRoutes.includes(href);
    link.style.display = allowed ? '' : 'none';
  });

  const currentPath = window.location.pathname;
  const isAllowedPath = allowedRoutes.some(route => currentPath === route || currentPath.startsWith(route + '/'));
  if(currentPath.startsWith('/template/') && !isAllowedPath){
    if(allowedRoutes.length > 0){
      window.location.href = allowedRoutes[0];
    }
  }
}

applyRoleBasedNavigation();

function setAuth(headers={}) {
  if(token) headers['Authorization'] = 'Bearer '+token;
  return headers;
}

// Only same-origin paths, so a crafted ?next= cannot redirect off-site.
function safeNextUrl(value){
  return value && /^\/(?!\/)/.test(value) ? value : null;
}

function handleAuthFailure(res){
  if(res.status !== 401) return false;
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  token = null;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  location.href = '/?expired=1&next=' + next;
  return true;
}

function getAllowedTransactionActions(role){
  const normalizedRole = (role || '').toLowerCase();
  if(normalizedRole === 'admin') return ['load', 'unload', 'process', 'sale'];
  if(normalizedRole === 'transporter') return ['load', 'unload'];
  if(normalizedRole === 'mill') return ['process', 'sale'];
  return [];
}

function renderBatchActionButtons(batchId){
  const actions = getAllowedTransactionActions(getCurrentRole());
  if(!actions.length) return '<span class="text-muted small">-</span>';

  return actions.map(action => {
    const label = action.charAt(0).toUpperCase() + action.slice(1);
    return `<button class="btn btn-sm btn-outline-primary me-1 mb-1" data-batch-action="${action}" data-batch-id="${batchId}">${label}</button>`;
  }).join('');
}

async function createBatchTransaction(batchId, type){
  const msg = document.getElementById('txMsg');
  const destinationId = document.getElementById('destinationOrgSelect')?.value;
  const vehicleId = document.getElementById('transactionVehicleSelect')?.value;
  const payload = {batch_id: batchId, type};

  if(type === 'unload' || type === 'sale'){
    if(!destinationId){
      if(msg){
        msg.textContent = 'Select a receiving organization first.';
        msg.className = 'mb-2 small text-danger';
      }
      return;
    }
    payload.to_org_id = Number(destinationId);
  }
  if(type === 'load' || type === 'unload'){
    if(!vehicleId){
      if(msg){
        msg.textContent = 'Select a vehicle first.';
        msg.className = 'mb-2 small text-danger';
      }
      return;
    }
    payload.vehicle_id = Number(vehicleId);
  }

  try {
    const res = await fetch(API + '/transactions', {
      method:'POST',
      headers:{'Content-Type':'application/json', ...setAuth()},
      body: JSON.stringify(payload)
    });

    const data = await res.json().catch(() => ({}));
    if(!res.ok){
      if(msg){
        msg.textContent = data.error || 'Failed to create transaction.';
        msg.className = 'mb-2 small text-danger';
      }
      return;
    }

    if(msg){
      msg.textContent = `Transaction '${type}' recorded for batch #${batchId}.`;
      msg.className = 'mb-2 small text-success';
    }

    await loadDashboard();
  } catch (_e) {
    if(msg){
      msg.textContent = 'Network error while recording transaction.';
      msg.className = 'mb-2 small text-danger';
    }
  }
}

// Login
if(document.getElementById('loginForm')){
  if(new URLSearchParams(window.location.search).get('expired')){
    const expiredMsg = document.getElementById('msg');
    if(expiredMsg) expiredMsg.textContent = 'Your session expired. Please sign in again.';
  }

  document.getElementById('loginForm').onsubmit = async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const res = await fetch(API + '/login', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email: fd.get('email'), password: fd.get('password')})
    });
    const data = await res.json();
    if(res.ok){
      token = data.token;
      localStorage.setItem('token', token);
      if(data.role) localStorage.setItem('role', data.role);
      const role = data.role || getCurrentRole();
      const allowedRoutes = getAllowedRoutesForRole(role);
      const requested = safeNextUrl(new URLSearchParams(window.location.search).get('next'));
      location.href = requested || allowedRoutes[0] || '/template/dashboard';
    } else {
      const msg = document.getElementById('msg');
      if(msg) msg.textContent = data.error || 'Login failed';
    }
  };
}

// Dashboard: load batches + counts
async function loadDashboard(){
  if(!document.getElementById('batchesBody')) return;
  const res = await fetch(API + '/batches', {headers:setAuth()});
  if(!res.ok){
    handleAuthFailure(res);
    return;
  }
  const data = await res.json();
  const tb = document.getElementById('batchesBody');
  tb.innerHTML = '';
  data.forEach(b => {
    const tr = document.createElement('tr');
    [b.unique_tag_id, b.species, b.volume_m3, b.current_status].forEach(value => {
      const cell = document.createElement('td');
      cell.textContent = value ?? '-';
      tr.appendChild(cell);
    });
    const actions = document.createElement('td');
    actions.innerHTML = renderBatchActionButtons(Number(b.id));
    tr.appendChild(actions);
    tb.appendChild(tr);
  });

  tb.querySelectorAll('button[data-batch-action]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const batchId = Number(btn.getAttribute('data-batch-id'));
      const action = btn.getAttribute('data-batch-action');
      await createBatchTransaction(batchId, action);
    });
  });
  if(document.getElementById('countBatches')) document.getElementById('countBatches').textContent = data.length;
  // latest block preview
  const latestBlockEl = document.getElementById('latestBlock');
  if(canViewBlockchain() && latestBlockEl){
    const brRes = await fetch(API + '/blockchain/latest', {headers:setAuth()}).catch(() => null);
    const br = brRes && brRes.ok ? await brRes.json().catch(() => null) : null;
    if(br && br.block_hash){
      latestBlockEl.textContent = `#${br.block_number} ${br.block_hash.slice(0,12)}...`;
    } else {
      latestBlockEl.textContent = 'Unavailable';
    }
  } else if(latestBlockEl){
    latestBlockEl.textContent = 'Restricted';
  }
}
if(document.getElementById('batchesBody')) loadDashboard();


/* New batch: load plots, filter permits, and submit the form */
if (document.getElementById('newBatchForm')) {
  const batchForm = document.getElementById('newBatchForm');
  const plotSelect = document.getElementById('plot_id');
  const permitSelect = document.getElementById('permit_id');
  const msg = document.getElementById('msg');

  let availablePlots = [];
  let availablePermits = [];

  function resetPermitDropdown(message) {
    permitSelect.replaceChildren(new Option(message, ''));
    permitSelect.disabled = true;
  }

  function filterPermitsForSelectedPlot() {
    const plot = availablePlots.find(
      p => String(p.id) === String(plotSelect.value)
    );

    if (!plot) {
      resetPermitDropdown('Select a forest plot first');
      return;
    }

    // Keep permits belonging to the selected plot's organization.
    const matchingPermits = availablePermits.filter(permit =>
      String(permit.org_id) === String(plot.org_id) &&
      permit.type === 'harvest' &&
      permit.status === 'active'
    );

    permitSelect.replaceChildren();

    if (matchingPermits.length === 0) {
      resetPermitDropdown('No active harvest permits available');
      return;
    }

    permitSelect.add(new Option('Select a harvest permit', ''));

    matchingPermits.forEach(permit => {
      permitSelect.add(
        new Option(permit.permit_number, permit.id)
      );
    });

    permitSelect.disabled = false;
  }

  async function loadBatchOptions() {
    resetPermitDropdown('Loading permits...');

    try {
      const [plotsResponse, permitsResponse] = await Promise.all([
        fetch(API + '/forest-plots', { headers: setAuth() }),
        fetch(API + '/permits?type=harvest', { headers: setAuth() })
      ]);

      if (!plotsResponse.ok || !permitsResponse.ok) {
        throw new Error('Failed to load forest plots or permits.');
      }

      availablePlots = await plotsResponse.json();
      availablePermits = await permitsResponse.json();

      plotSelect.replaceChildren(
        new Option('Select a forest plot', '')
      );

      availablePlots.forEach(plot => {
        plotSelect.add(new Option(plot.name, plot.id));
      });

      filterPermitsForSelectedPlot();

    } catch (error) {
      console.error('Failed to load batch options:', error);

      plotSelect.replaceChildren(
        new Option('Unable to load forest plots', '')
      );

      resetPermitDropdown('Unable to load permits');

      if (msg) {
        msg.textContent = 'Could not load form options. Please try again.';
        msg.className = 'mt-2 text-danger';
      }
    }
  }

  // Update the permit list whenever the plot changes.
  plotSelect.addEventListener(
    'change',
    filterPermitsForSelectedPlot
  );

  // Load dropdown options when the form is initialized.
  loadBatchOptions();

  // Submit the batch.
  batchForm.onsubmit = async e => {
    e.preventDefault();

    const plot = availablePlots.find(
      p => String(p.id) === String(plotSelect.value)
    );

    const permit = availablePermits.find(
      p => String(p.id) === String(permitSelect.value)
    );

    // Frontend validation for a better user experience.
    if (!plot || !permit ||
        String(plot.org_id) !== String(permit.org_id) ||
        permit.type !== 'harvest' ||
        permit.status !== 'active') {
      if (msg) {
        msg.textContent =
          'Select a valid forest plot and its organization’s active harvest permit.';
        msg.className = 'mt-2 text-danger';
      }
      return;
    }

    const fd = new FormData(batchForm);
    const data = Object.fromEntries(fd);

    try {
      const res = await fetch(API + '/batches', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...setAuth()
        },
        body: JSON.stringify(data)
      });

      const result = await res.json().catch(() => ({}));

      if (!res.ok) {
        if (msg) {
          msg.textContent = result.error || 'Failed to create batch.';
          msg.className = 'mt-2 text-danger';
        }
        return;
      }

      if (msg) {
        msg.textContent = 'Batch created: ' + result.unique_tag_id;
        msg.className = 'mt-2 text-success';
      }

      batchForm.reset();
      filterPermitsForSelectedPlot();

    } catch (error) {
      console.error('Batch submission failed:', error);

      if (msg) {
        msg.textContent = 'Network error while creating the batch.';
        msg.className = 'mt-2 text-danger';
      }
    }
  };
}

// Track batch
if(document.getElementById('searchBtn')){
  let activeTrackedBatchId = null;
  const trackRole = (getCurrentRole() || '').toLowerCase();
  const transactionOptions = document.getElementById('transactionOptions');
  const destinationWrap = document.getElementById('destinationWrap');
  const vehicleWrap = document.getElementById('vehicleWrap');
  const destinationSelect = document.getElementById('destinationOrgSelect');
  const vehicleSelect = document.getElementById('transactionVehicleSelect');

  const appendSelectOptions = (select, rows, label, placeholder) => {
    select.replaceChildren(new Option(placeholder, ''));
    rows.forEach(row => select.add(new Option(label(row), row.id)));
  };

  
const loadTransactionOptions = async () => {
  const role = (getCurrentRole() || '').toLowerCase();

  const fetchRows = async (path) => {
    const res = await fetch(API + path, { headers: setAuth() });
    if (!res.ok) {
      if (handleAuthFailure(res)) return [];
      throw new Error(`Could not load options from ${path}`);
    }
    return res.json();
  };

  let vehicles = [];
  let destinations = [];

  if (role === 'transporter' || role === 'admin') {
    vehicles = await fetchRows('/vehicles');
  }

  if (role === 'transporter') {
    destinations = await fetchRows(
      '/recipient-organizations?type=mill'
    );
  } else if (role === 'mill') {
    destinations = await fetchRows(
      '/recipient-organizations?type=buyer'
    );
  } else if (role === 'admin') {
    const [mills, buyers] = await Promise.all([
      fetchRows('/recipient-organizations?type=mill'),
      fetchRows('/recipient-organizations?type=buyer')
    ]);

    destinations = [
      ...mills.map(org => ({ ...org, name: `${org.name} (Mill)` })),
      ...buyers.map(org => ({ ...org, name: `${org.name} (Buyer)` }))
    ];
  } else {
    return;
  }

  if (vehicleSelect && (role === 'transporter' || role === 'admin')) {
    appendSelectOptions(
      vehicleSelect,
      vehicles,
      item => `${item.plate_number} (${item.capacity_m3 ?? '?'} m³)`,
      'Select vehicle'
    );

    vehicleWrap.hidden = false;
  }

  if (destinationSelect) {
    appendSelectOptions(
      destinationSelect,
      destinations,
      item => item.name,
      'Select receiving organization'
    );

    destinationWrap.hidden = false;
  }

  if (transactionOptions) {
    transactionOptions.hidden = false;
  }
};


  const renderTrackActionButtons = (batchId) => {
    activeTrackedBatchId = batchId;
    const roleActions = getAllowedTransactionActions(getCurrentRole());
    const wrap = document.getElementById('actionButtons');
    if(!wrap) return;

    const actionMap = {
      load: document.getElementById('loadBtn'),
      unload: document.getElementById('unloadBtn'),
      process: document.getElementById('processBtn'),
      sale: document.getElementById('saleBtn')
    };

    Object.entries(actionMap).forEach(([action, btn]) => {
      if(!btn) return;
      btn.hidden = !roleActions.includes(action);
      btn.onclick = async () => {
        if(activeTrackedBatchId){
          await createBatchTransaction(activeTrackedBatchId, action);
        }
      };
    });

    wrap.hidden = roleActions.length === 0;
  };

  const loadTrackByTag = async (tag) => {
    const normalizedTag = (tag || '').trim();
    if(!normalizedTag) return;

    const res = await fetch(API + '/batches/by-tag/' + encodeURIComponent(normalizedTag), {headers:setAuth()});
    if(!res.ok){
      if(handleAuthFailure(res)) return;
      const problem = await res.json().catch(() => ({}));
      alert(problem.error || (res.status === 403
        ? 'You are not authorised to view this batch.'
        : 'No batch found with that tag.'));
      return;
    }
    const batch = await res.json();

    document.getElementById('result').hidden = false;
    document.getElementById('batchTag').textContent = batch.unique_tag_id;
    document.getElementById('batchSpecies').textContent = batch.species;
    document.getElementById('batchVolume').textContent = batch.volume_m3;
    document.getElementById('batchStatus').textContent = batch.current_status;
    document.getElementById('batchHarvestDate').textContent = batch.harvest_date || '-';
    document.getElementById('batchPlot').textContent = batch.plot?.name || '-';
    document.getElementById('batchHolder').textContent = batch.current_holder_name || '-';
    renderTrackActionButtons(batch.id);

    const txRes = await fetch(API + '/transactions?batch_id=' + batch.id, {headers:setAuth()});
    const txs = await txRes.json();
    const tb = document.getElementById('txBody');
    tb.innerHTML = '';
    txs.forEach(t => {
      const tr = document.createElement('tr');
      const loc = t.location_lat && t.location_lon ? `${t.location_lat},${t.location_lon}` : '—';
      tr.innerHTML = `<td>${t.type}</td><td>${t.from_user_id||'-'}</td><td>${t.to_user_id||'-'}</td><td>${t.timestamp ? new Date(t.timestamp).toLocaleString() : '-'}</td><td>${loc}</td>`;
      tb.appendChild(tr);
    });

    if(canViewBlockchain()){
      const brRes = await fetch(API + '/blockchain/latest', {headers:setAuth()}).catch(()=>null);
      const br = brRes && brRes.ok ? await brRes.json().catch(()=>null) : null;
      if(br){
        document.getElementById('blockInfo').textContent = JSON.stringify(br, null, 2);
      }
    } else {
      document.getElementById('blockInfo').textContent = 'Blockchain data is restricted for your role.';
    }
  };

  document.getElementById('searchBtn').onclick = async () => {
    const tagInputVal = document.getElementById('tagInput').value.trim();
    await loadTrackByTag(tagInputVal);
  };

  const scanBtn = document.getElementById('scanBtn');
  if(scanBtn){
    let html5QrCode = null;


  loadTransactionOptions().catch(() => {
    const message = document.getElementById('txMsg');
    if(message) message.textContent = 'Transaction options could not be loaded.';
  });
    scanBtn.addEventListener('click', async () => {
      const scannerWrap = document.getElementById('scannerWrap');
      const scanResult = document.getElementById('scanResult');
      if(!scannerWrap || !scanResult) return;

      scannerWrap.hidden = false;
      scanResult.textContent = 'Starting camera...';

      try {
        if(!window.Html5Qrcode){
          scanResult.textContent = 'QR scanner library not loaded. Refresh and try again.';
          return;
        }

        if(!html5QrCode){
          html5QrCode = new Html5Qrcode('scanner');
        }

        const cameras = await Html5Qrcode.getCameras();
        if(!cameras || cameras.length === 0){
          scanResult.textContent = 'No camera found on this device.';
          return;
        }

        await html5QrCode.start(
          { facingMode: 'environment' },
          { fps: 10, qrbox: { width: 240, height: 240 } },
          async (decodedText) => {
            let tagId = extractTagIdFromScannedText(decodedText);
            try {
              const scannedUrl = new URL(decodedText, window.location.origin);
              const tokenMatch = scannedUrl.pathname.match(/\/scan\/([^/]+)\/?$/);
              if(tokenMatch){
                const tokenResponse = await fetch(
                  API + '/scan/' + encodeURIComponent(tokenMatch[1]),
                  {headers:setAuth()}
                );
                const tokenResult = await tokenResponse.json().catch(() => ({}));
                if(!tokenResponse.ok){
                  if(handleAuthFailure(tokenResponse)) return;
                  scanResult.textContent = tokenResult.error || 'This QR code could not be verified.';
                  return;
                }
                tagId = tokenResult.unique_tag_id;
              }
            } catch (_e) {
              tagId = extractTagIdFromScannedText(decodedText);
            }

            if(!tagId){
              scanResult.textContent = 'Scanned QR is not recognized.';
              return;
            }

            scanResult.textContent = 'Scanned tag: ' + tagId;
            document.getElementById('tagInput').value = tagId;

            await html5QrCode.stop().catch(() => {});
            scannerWrap.hidden = true;
            await loadTrackByTag(tagId);
          },
          (_errorMessage) => {
            // Ignore noisy frame decode errors.
          }
        );
      } catch (err) {
        scanResult.textContent = 'Scanner error: ' + (err?.message || err);
      }
    });
  }

  // Load a batch automatically when the URL contains ?tag=...
  const initialTag = new URLSearchParams(window.location.search).get('tag');

  if (initialTag) {
    const tagInput = document.getElementById('tagInput');

    if (tagInput) {
      tagInput.value = initialTag;
      loadTrackByTag(initialTag);
    }
  }

loadTransactionOptions().catch(err => {
    console.error('Transaction options failed to load:', err);

    const msg = document.getElementById('txMsg');
    if (msg) {
      msg.textContent =
        'Could not load vehicles or receiving organizations. Refresh and try again.';
      msg.className = 'mb-2 small text-danger';
    }
  });
}


// Users page
if(document.getElementById('usersBody')){
  (async ()=>{
    const res = await fetch(API + '/users', {headers:setAuth()});
    const payload = await res.json().catch(()=>({}));
    const tb = document.getElementById('usersBody');
    const msg = document.getElementById('usersMsg');
    tb.innerHTML='';

    if(!res.ok){
      if(handleAuthFailure(res)) return;
      if(msg) msg.textContent = payload.error || 'Unable to load users.';
      return;
    }

    const users = Array.isArray(payload) ? payload : [];
    if(users.length === 0){
      if(msg) msg.textContent = 'No users found.';
      return;
    }

    if(msg) msg.textContent = '';
    users.forEach(u => {
      const tr = document.createElement('tr');
      [u.name, u.email, formatRole(u.role), u.phone || '-'].forEach(value => {
        const cell = document.createElement('td');
        cell.textContent = value;
        tr.appendChild(cell);
      });
      tb.appendChild(tr);
    });
  })();

  document.getElementById('addUserForm').onsubmit = async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const data = Object.fromEntries(fd);
    const res = await fetch(API + '/register', {
      method:'POST',
      headers:{'Content-Type':'application/json', ...setAuth()},
      body: JSON.stringify(data)
    });
    const j = await res.json();
    if(res.ok){
      alert('User created');
      location.reload();
    } else {
      alert(j.error || 'Failed');
    }
  };
}

// Blockchain batch custody timeline
if(document.getElementById('blockchainBatchLookupForm')){
  const lookupForm = document.getElementById('blockchainBatchLookupForm');
  const lookupInput = document.getElementById('blockchainBatchTag');
  const lookupMessage = document.getElementById('blockchainBatchLookupMessage');
  const resultPanel = document.getElementById('batchChainResult');
  const eventsBody = document.getElementById('batchChainEvents');

  const appendCell = (row, value, className='') => {
    const cell = document.createElement('td');
    cell.textContent = value ?? '-';
    if(className) cell.className = className;
    row.appendChild(cell);
    return cell;
  };

  const findBatchChain = async (tag) => {
    const normalizedTag = (tag || '').trim();
    if(!normalizedTag) return;

    lookupMessage.className = 'small mb-3 text-muted';
    lookupMessage.textContent = 'Loading batch custody chain…';
    resultPanel.hidden = true;

    try {
      const response = await fetch(
        API + '/blockchain/batch/' + encodeURIComponent(normalizedTag),
        {headers:setAuth()}
      );
      const data = await response.json().catch(() => ({}));
      if(!response.ok){
        if(handleAuthFailure(response)) return;
        lookupMessage.className = 'small mb-3 text-danger';
        lookupMessage.textContent = data.error || 'Batch could not be found.';
        return;
      }

      document.getElementById('chainBatchTag').textContent = data.batch.unique_tag_id;
      document.getElementById('chainBatchSummary').textContent =
        `${data.batch.species} · ${data.batch.volume_m3} m³ · harvested ${data.batch.harvest_date || '-'}`;
      document.getElementById('chainBatchStatus').textContent = data.batch.current_status;
      document.getElementById('chainBatchHolder').textContent =
        `Current holder: ${data.batch.current_holder || '-'} · Plot: ${data.batch.plot || '-'}`;
      document.getElementById('chainEventCount').textContent =
        `${data.transaction_count} custody ${data.transaction_count === 1 ? 'event' : 'events'} · ordered oldest to newest`;

      eventsBody.replaceChildren();
      data.transactions.forEach(event => {
        const row = document.createElement('tr');
        appendCell(row, `${event.position}. ${event.type}`);
        appendCell(row, event.occurred_at ? new Date(event.occurred_at).toLocaleString() : '-');
        appendCell(row, event.actor || '-');
        appendCell(row, `${event.from_org || '-'} → ${event.to_org || '-'}`);

        const blockCell = appendCell(row, '');
        if(event.anchored){
          const blockNumber = document.createElement('strong');
          blockNumber.textContent = `#${event.block_number}`;
          const blockHash = document.createElement('div');
          blockHash.className = 'font-monospace text-muted small text-break';
          blockHash.textContent = event.block_hash;
          blockCell.append(blockNumber, blockHash);
        } else {
          const pending = document.createElement('span');
          pending.className = 'badge text-bg-warning';
          pending.textContent = 'Pending';
          blockCell.appendChild(pending);
        }

        const checksCell = appendCell(row, '');
        const hashCheck = document.createElement('span');
        hashCheck.className = event.hash_valid ? 'badge text-bg-success me-1' : 'badge text-bg-danger me-1';
        hashCheck.textContent = event.hash_valid ? 'Hash valid' : 'Hash issue';
        checksCell.appendChild(hashCheck);
        if(event.anchored){
          const membershipCheck = document.createElement('span');
          membershipCheck.className = event.membership_matches ? 'badge text-bg-success' : 'badge text-bg-danger';
          membershipCheck.textContent = event.membership_matches ? 'Included' : 'Membership issue';
          checksCell.appendChild(membershipCheck);
        }
        eventsBody.appendChild(row);
      });

      document.getElementById('batchChainEmpty').hidden = data.transaction_count !== 0;
      lookupMessage.textContent = '';
      resultPanel.hidden = false;
    } catch (_error) {
      lookupMessage.className = 'small mb-3 text-danger';
      lookupMessage.textContent = 'Network error while loading the batch chain.';
    }
  };

  lookupForm.addEventListener('submit', event => {
    event.preventDefault();
    findBatchChain(lookupInput.value);
  });

  const initialTag = new URLSearchParams(window.location.search).get('tag');
  if(initialTag){
    lookupInput.value = initialTag;
    findBatchChain(initialTag);
  }

  document.getElementById('verifyBtn').onclick = async () => {
    const status = document.getElementById('ledgerVerificationResult');
    status.textContent = 'Verifying…';
    const response = await fetch(API + '/blockchain/verify', {headers:setAuth()});
    const data = await response.json().catch(() => ({}));
    if(handleAuthFailure(response)) return;
    status.textContent = data.valid
      ? `Ledger valid · ${data.total_blocks} blocks`
      : `Ledger verification failed · ${data.error || 'integrity mismatch'}`;
    status.className = data.valid ? 'small text-success' : 'small text-danger';
  };
}
//Blockchain Verifier
const verifyButton = document.getElementById("verifyBtn");
const verificationResult = document.getElementById(
  "ledgerVerificationResult"
);

if (verifyButton && verificationResult) {
  verifyButton.addEventListener("click", async () => {
    verifyButton.disabled = true;
    verificationResult.className = "small text-muted";
    verificationResult.textContent = "Verifying ledger…";

    try {
      const response = await fetch(`${API}/blockchain/verify`, {
        method: "GET",
        headers: setAuth()
      });

      const result = await response.json();

    if (result.valid === false) {
      verificationResult.className = "small text-danger";
      verificationResult.textContent =
        `Verification failed: ${result.error || "Ledger integrity check failed."}`;

    } else if (!response.ok) {
      verificationResult.className = "small text-danger";
      verificationResult.textContent =
        result.error || `Verification request failed (${response.status}).`;

    } else if (result.valid === true) {
      const fields = [
        "blocks_checked",
        "transactions_checked",
        "unanchored_transactions"
      ];

      const missingOrInvalid = fields.filter(
        field => !Number.isInteger(result[field]) || result[field] < 0
      );

      if (missingOrInvalid.length > 0) {
        verificationResult.className = "small text-warning";
        verificationResult.textContent =
          "The server reported a valid ledger, but returned incomplete " +
          "verification statistics. Check the API response.";

        console.error("Invalid verification response:", result);
      } else {
        verificationResult.className = "small text-success";
        verificationResult.textContent =
          `Valid: checked ${result.blocks_checked} blocks and ` +
          `${result.transactions_checked} transactions. ` +
          `${result.unanchored_transactions} transactions are not yet anchored.`;
      }

    } else {
      verificationResult.className = "small text-danger";
      verificationResult.textContent =
        "The server returned an unexpected verification response.";

      console.error("Unexpected verification response:", result);
    }
        } catch (error) {
          verificationResult.className = "small text-danger";
          verificationResult.textContent =
            "Could not verify the ledger. Check your connection and try again.";
          console.error("Ledger verification error:", error);
        } finally {
          verifyButton.disabled = false;
        }
      });
    }

// Logout (supports header and sidebar controls)
document.querySelectorAll('[data-logout="true"], #logoutLink').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    location.href = '/';
  });
});