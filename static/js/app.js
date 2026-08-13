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

function getAllowedRoutesForRole(role){
  const normalizedRole = (role || '').toLowerCase();
  const roleNavMap = {
    admin: ['/template/dashboard', '/template/track', '/template/new-batch', '/template/users', '/template/blockchain', '/template/settings'],
    logger: ['/template/new-batch'],
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
  const userId = getCurrentUserId();

  try {
    const res = await fetch(API + '/transactions', {
      method:'POST',
      headers:{'Content-Type':'application/json', ...setAuth()},
      body: JSON.stringify({
        batch_id: batchId,
        type,
        from_user_id: userId,
        to_user_id: userId
      })
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
      location.href = allowedRoutes[0] || '/template/dashboard';
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
  const data = await res.json();
  const tb = document.getElementById('batchesBody');
  tb.innerHTML = '';
  data.forEach(b => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${b.unique_tag_id}</td><td>${b.species}</td><td>${b.volume_m3}</td><td>${b.current_status}</td><td>${renderBatchActionButtons(b.id)}</td>`;
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

// New batch
if(document.getElementById('newBatchForm')){
  document.getElementById('newBatchForm').onsubmit = async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const data = Object.fromEntries(fd);
    const res = await fetch(API + '/batches', {
      method:'POST',
      headers:{'Content-Type':'application/json', ...setAuth()},
      body: JSON.stringify(data)
    });
    const j = await res.json();
    const msg = document.getElementById('msg');
    if(res.ok){
      msg.textContent = 'Batch created: ' + j.unique_tag_id;
      msg.className = 'mt-2 text-success';
      e.target.reset();
    } else {
      msg.textContent = j.error || 'Failed';
      msg.className = 'mt-2 text-danger';
    }
  };
}

// Track batch
if(document.getElementById('searchBtn')){
  let activeTrackedBatchId = null;

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
      alert('Batch not found or access denied.');
      return;
    }
    const batch = await res.json();

    document.getElementById('result').hidden = false;
    document.getElementById('batchTag').textContent = batch.unique_tag_id;
    document.getElementById('batchSpecies').textContent = batch.species;
    document.getElementById('batchVolume').textContent = batch.volume_m3;
    document.getElementById('batchStatus').textContent = batch.current_status;
    renderTrackActionButtons(batch.id);

    const txRes = await fetch(API + '/transactions?batch_id=' + batch.id, {headers:setAuth()});
    const txs = await txRes.json();
    const tb = document.getElementById('txBody');
    tb.innerHTML = '';
    txs.forEach(t => {
      const tr = document.createElement('tr');
      const loc = t.location_lat && t.location_lon ? `${t.location_lat},${t.location_lon}` : '—';
      tr.innerHTML = `<td>${t.type}</td><td>${t.from_user_id||'-'}</td><td>${t.to_user_id||'-'}</td><td>${new Date(t.timestamp).toLocaleString()}</td><td>${loc}</td>`;
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
            const tagId = extractTagIdFromScannedText(decodedText);
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
      if(msg) msg.textContent = payload.error || 'Unable to load users.';
      if(res.status === 401){
        localStorage.removeItem('token');
        setTimeout(() => { location.href = '/'; }, 700);
      }
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
      tr.innerHTML = `<td>${u.name}</td><td>${u.email}</td><td>${u.role}</td><td>${u.phone||'-'}</td>`;
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

// Blockchain page
if(document.getElementById('bcOutput')){
  document.getElementById('latestBtn').onclick = async () => {
    const r = await fetch(API + '/blockchain/latest', {headers:setAuth()});
    const j = await r.json();
    document.getElementById('bcOutput').textContent = JSON.stringify(j, null, 2);
  };
  document.getElementById('chainBtn').onclick = async () => {
    const r = await fetch(API + '/blockchain/chain', {headers:setAuth()});
    const j = await r.json();
    document.getElementById('bcOutput').textContent = JSON.stringify(j, null, 2);
  };
  document.getElementById('verifyBtn').onclick = async () => {
    const r = await fetch(API + '/blockchain/verify', {headers:setAuth()});
    const j = await r.json();
    document.getElementById('bcOutput').textContent = JSON.stringify(j, null, 2);
  };
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