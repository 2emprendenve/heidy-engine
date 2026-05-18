// app.js — Heidy Engine Control Panel v4

// ─── 1. QUANTITY SELECTOR ────────────────────────────────────
let _selectedQty = 10;

function initQtyPills() {
    const container = document.getElementById('qty-pills');
    const quantities = [10, 15, 20, 25, 30, 35, 40, 45, 50];
    container.innerHTML = quantities.map(n => `
        <button class="qty-pill ${n === _selectedQty ? 'active' : ''}"
                onclick="selectQty(${n})" id="pill-${n}">
            ${n}
        </button>
    `).join('');
}

function selectQty(n) {
    _selectedQty = n;
    document.querySelectorAll('.qty-pill').forEach(p => p.classList.remove('active'));
    document.getElementById(`pill-${n}`).classList.add('active');
    document.getElementById('btn-main-sub').textContent =
        `Redacta ${n} correos con Gemini · revisa · aprueba · envía`;
}

// ─── 2. STATS ────────────────────────────────────────────────
async function loadStats() {
    try {
        const res  = await fetch('/api/action/leads_disponibles');
        const data = await res.json();
        if (data.status === 'success') {
            document.getElementById('val-totales').textContent = data.total ?? '—';
        }
    } catch (e) { console.error('loadStats', e); }
}

// ─── 3. ACCIONES SECUNDARIAS ─────────────────────────────────
async function triggerAction(actionName) {
    showToast('⏳ ' + actionName.replace(/_/g, ' ') + '...');
    try {
        const res  = await fetch(
            actionName === 'leads_disponibles'
                ? '/api/action/leads_disponibles'
                : `/api/action/${actionName}`,
            { method: actionName === 'leads_disponibles' ? 'GET' : 'POST' }
        );
        const data = await res.json();
        if (data.status === 'success') {
            if (actionName === 'leads_disponibles') {
                showToast(`✅ ${data.total} leads en base · ${data.listos ?? data.total} disponibles`);
                document.getElementById('val-totales').textContent = data.total;
            } else {
                showToast('✅ ' + (data.message || 'Completado.'));
            }
        } else {
            showToast('❌ ' + (data.message || 'Error.'));
        }
    } catch (e) {
        showToast('❌ Error de red: ' + e.message);
    }
}

// ─── 4. TOAST ────────────────────────────────────────────────
let _toastTimer;
function showToast(message) {
    const toast = document.getElementById('toast');
    let icon = '🔔';
    if (message.startsWith('✅')) { icon = '✅'; message = message.slice(1).trim(); }
    if (message.startsWith('❌')) { icon = '❌'; message = message.slice(1).trim(); }
    if (message.startsWith('⏳')) { icon = '⏳'; message = message.slice(1).trim(); }
    document.getElementById('toast-icon').textContent    = icon;
    document.getElementById('toast-message').textContent = message;
    toast.classList.remove('hidden');
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => toast.classList.add('hidden'), 6000);
}

// ─── 5. SSE LOG STREAM ───────────────────────────────────────
function initLogStream() {
    const container = document.getElementById('log-container');
    const evtSource = new EventSource('/api/logs');
    evtSource.onmessage = e => {
        const div = document.createElement('div');
        div.className   = 'log-line';
        div.textContent = e.data;
        container.appendChild(div);
        if (container.childNodes.length > 100) container.removeChild(container.firstChild);
        container.scrollTop = container.scrollHeight;
    };
}

// ─── 6. DRAFT REVIEW SYSTEM ──────────────────────────────────
let _drafts   = [];
let _approved = new Set();

async function openDraftModal() {
    const modal = document.getElementById('draft-modal');
    modal.classList.add('open');

    document.getElementById('draft-subtitle').textContent =
        `Generando ${_selectedQty} correos con Gemini — espera unos segundos...`;
    document.getElementById('draft-list').innerHTML =
        '<div style="text-align:center;color:#64748b;padding:60px;font-size:22px;">⏳</div>';

    _drafts   = [];
    _approved = new Set();
    updateApprovedUI();

    try {
        const res  = await fetch('/api/drafts/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ n: _selectedQty })
        });
        const data = await res.json();

        if (data.status !== 'success') {
            document.getElementById('draft-subtitle').textContent = '❌ ' + data.message;
            document.getElementById('draft-list').innerHTML =
                `<p style="color:#ef4444;text-align:center;">${escHtml(data.message)}</p>`;
            return;
        }

        _drafts = data.drafts;
        document.getElementById('draft-subtitle').textContent =
            `${data.total} correos listos — revisa en preview, aprueba los que te gusten y envía.`;
        renderDraftList();

    } catch (e) {
        document.getElementById('draft-subtitle').textContent = '❌ Error: ' + e.message;
    }
}

function closeDraftModal() {
    document.getElementById('draft-modal').classList.remove('open');
}

function renderDraftList() {
    const container = document.getElementById('draft-list');
    if (!_drafts.length) {
        container.innerHTML = '<p style="color:#64748b;text-align:center;">No se generaron borradores.</p>';
        return;
    }
    container.innerHTML = _drafts.map((d, i) => `
        <div class="draft-card ${_approved.has(i) ? 'approved' : ''}" id="card-${i}">
            <div class="draft-info">
                <div class="company">${escHtml(d.empresa)}</div>
                <div class="email">✉️ ${escHtml(d.email)}</div>
                <div class="subject">📌 ${escHtml(d.subject)}</div>
            </div>
            <div class="draft-actions">
                <button class="btn-preview" onclick="openPreview(${i}, '${escAttr(d.empresa)}')">👁 Ver</button>
                <button class="btn-approve ${_approved.has(i) ? 'active' : ''}"
                        onclick="toggleApprove(${i})" id="btn-app-${i}">
                    ${_approved.has(i) ? '✅ Aprobado' : '✓ Aprobar'}
                </button>
            </div>
        </div>
    `).join('');
}

function toggleApprove(idx) {
    if (_approved.has(idx)) { _approved.delete(idx); }
    else                     { _approved.add(idx);    }
    const card = document.getElementById(`card-${idx}`);
    const btn  = document.getElementById(`btn-app-${idx}`);
    if (_approved.has(idx)) {
        card.classList.add('approved');
        btn.textContent = '✅ Aprobado';
        btn.classList.add('active');
    } else {
        card.classList.remove('approved');
        btn.textContent = '✓ Aprobar';
        btn.classList.remove('active');
    }
    updateApprovedUI();
}

function approveAll() {
    _drafts.forEach((_, i) => _approved.add(i));
    renderDraftList();
    updateApprovedUI();
}

function updateApprovedUI() {
    const count  = _approved.size;
    const sendBtn = document.getElementById('btn-send-all');
    document.getElementById('approved-count').textContent = count;
    if (count > 0) {
        sendBtn.classList.add('ready');
        sendBtn.textContent = `🚀 Enviar ${count} Aprobado${count > 1 ? 's' : ''}`;
    } else {
        sendBtn.classList.remove('ready');
        sendBtn.textContent = '🚀 Enviar 0 Aprobados';
    }
}

// ─── 7. CONFIRM & SEND ───────────────────────────────────────
function confirmSend() {
    if (_approved.size === 0) {
        showToast('⚠️ Aprueba al menos 1 borrador.');
        return;
    }
    const count = _approved.size;
    document.getElementById('confirm-text').innerHTML =
        `¿Confirmar envío de <b style="color:#4ade80">${count} correo${count > 1 ? 's' : ''}</b> a leads reales?<br>
         <span style="color:#ef4444;font-size:12px;">Esta acción no se puede deshacer.</span>`;
    document.getElementById('confirm-modal').classList.add('open');
}

function closeConfirm() {
    document.getElementById('confirm-modal').classList.remove('open');
}

async function sendApprovedDrafts() {
    closeConfirm();
    if (_approved.size === 0) return;

    showToast('⏳ Aprobando borradores...');

    // 1. Marcar aprobados en el servidor
    const approveRes  = await fetch('/api/drafts/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ indices: Array.from(_approved) })
    });
    const approveData = await approveRes.json();
    if (approveData.status !== 'success') {
        showToast('❌ Error aprobando: ' + approveData.message);
        return;
    }

    // 2. Enviar
    showToast('⏳ Enviando correos...');
    const sendRes  = await fetch('/api/drafts/send', { method: 'POST' });
    const sendData = await sendRes.json();

    if (sendData.status === 'success') {
        showToast('✅ ' + sendData.message);
        closeDraftModal();
        loadStats();
        document.getElementById('val-enviados').textContent =
            parseInt(document.getElementById('val-enviados').textContent || '0')
            + (sendData.enviados || 0);
    } else {
        showToast('❌ ' + sendData.message);
    }
}

// ─── 8. EMAIL PREVIEW ────────────────────────────────────────
function openPreview(idx, empresa) {
    document.getElementById('preview-label').textContent = '📧 ' + empresa;
    document.getElementById('preview-iframe').src = `/api/drafts/preview/${idx}`;
    document.getElementById('preview-modal').classList.add('open');
}

function closePreview() {
    document.getElementById('preview-modal').classList.remove('open');
    document.getElementById('preview-iframe').src = 'about:blank';
}

// ─── Helpers ─────────────────────────────────────────────────
function escHtml(str) {
    return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function escAttr(str) {
    return String(str || '').replace(/'/g,"\\'").replace(/"/g,'\\"');
}

// ─── 9. METRICS MODAL ────────────────────────────────────────
async function openMetricsModal() {
    const modal = document.getElementById('metrics-modal');
    modal.classList.add('open');
    const content = document.getElementById('metrics-content');
    content.innerHTML = '<div style="text-align:center; color:#64748b; padding:40px;">⏳ Obteniendo datos reales de Sheets y Buzón...</div>';

    try {
        const res = await fetch('/api/metrics');
        const data = await res.json();
        
        let html = `
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
                <div>
                    <h4 style="color:#60a5fa; margin-bottom:8px; border-bottom:1px solid #2a2a4a; padding-bottom:4px; font-size:16px; margin-top:0;">📊 FASE 1 (Apertura)</h4>
                    Total Leads Base: <b style="float:right;">${data.total_leads || 0}</b><br>
                    Correos Enviados: <b style="color:#e2e8f0; float:right;">${data.f1_enviados || 0}</b><br>
                    Aperturas: <b style="color:#4ade80; float:right;">${data.f1_aperturas || 0}</b><br>
                    Rebotes: <b style="color:#ef4444; float:right;">${data.f1_rebotes || 0}</b>
                </div>
                <div>
                    <h4 style="color:#60a5fa; margin-bottom:8px; border-bottom:1px solid #2a2a4a; padding-bottom:4px; font-size:16px; margin-top:0;">🎯 FASE 2 (Cierre)</h4>
                    Interesados (Clics): <b style="color:#fbbf24; float:right;">${data.f2_interes || 0}</b><br>
                    Propuestas Enviadas: <b style="color:#e2e8f0; float:right;">${data.f2_enviados || 0}</b><br>
                    Aperturas: <b style="color:#4ade80; float:right;">${data.f2_aperturas || 0}</b><br>
                    Vendidos: <b style="color:#10b981; float:right;">${data.f2_vendidos || 0}</b>
                </div>
            </div>
            <div style="margin-top:16px; border-top:1px solid #2a2a4a; padding-top:12px; font-size:13px; color:#94a3b8; text-align:center;">
                Estado del Motor: <b>${data.estado || 'DETENIDO'}</b>
            </div>
        `;
        content.innerHTML = html;
    } catch (e) {
        content.innerHTML = '<div style="color:#ef4444; padding:20px; text-align:center;">❌ Error cargando métricas: ' + escHtml(e.message) + '</div>';
    }
}

function closeMetricsModal() {
    document.getElementById('metrics-modal').classList.remove('open');
}

// ─── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initQtyPills();
    loadStats();
    initLogStream();
    setInterval(loadStats, 60000);

    // Cerrar modales al hacer clic fuera
    ['draft-modal', 'preview-modal', 'confirm-modal', 'metrics-modal'].forEach(id => {
        document.getElementById(id).addEventListener('click', function(e) {
            if (e.target === this) {
                if (id === 'draft-modal')   closeDraftModal();
                if (id === 'preview-modal') closePreview();
                if (id === 'confirm-modal') closeConfirm();
                if (id === 'metrics-modal') closeMetricsModal();
            }
        });
    });
});
