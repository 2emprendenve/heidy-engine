const elements = {
    f1Enviados: document.getElementById('stat-f1-enviados'),
    f1Aperturas: document.getElementById('stat-f1-aperturas'),
    f1Rebotes: document.getElementById('stat-f1-rebotes'),
    f1Eliminados: document.getElementById('stat-f1-eliminados'),
    f2Interes: document.getElementById('stat-f2-interes'),
    f2Enviados: document.getElementById('stat-f2-enviados'),
    f2Aperturas: document.getElementById('stat-f2-aperturas'),
    f2Vendidos: document.getElementById('stat-f2-vendidos'),
    statusText: document.getElementById('status-text'),
    statusBadge: document.getElementById('motor-status'),
    promptApertura: document.getElementById('prompt-apertura-editor'),
    promptCierre: document.getElementById('prompt-cierre-editor'),
    savePromptsBtn: document.getElementById('save-prompts'),
    toggleMotorBtn: document.getElementById('toggle-motor'),
    logContainer: document.getElementById('log-container'),
    testEmailInput: document.getElementById('test-email-input'),
    sendTestBtn: document.getElementById('send-test-btn'),
    tabBtns: document.querySelectorAll('.tab-btn'),
    aperturaWrap: document.getElementById('apertura-editor-wrap'),
    cierreWrap: document.getElementById('cierre-editor-wrap')
};

const API_BASE = 'http://localhost:5000/api';

// ─────────────────────────────────────────────────────────
// MÉTRICAS Y ESTADO
// ─────────────────────────────────────────────────────────
async function fetchMetrics() {
    try {
        const resp = await fetch(`${API_BASE}/metrics`);
        const data = await resp.json();

        elements.f1Enviados.innerText = data.f1_enviados || 0;
        elements.f1Aperturas.innerText = data.f1_aperturas || 0;
        elements.f1Rebotes.innerText = data.f1_rebotes || 0;
        elements.f1Eliminados.innerText = data.f1_eliminados || 0;
        elements.f2Interes.innerText = data.f2_interes || 0;
        elements.f2Enviados.innerText = data.f2_enviados || 0;
        elements.f2Aperturas.innerText = data.f2_aperturas || 0;
        elements.f2Vendidos.innerText = data.f2_vendidos || 0;

        if (data.active) {
            elements.statusText.innerText = 'Ejecutando';
            elements.statusBadge.classList.add('active');
            elements.toggleMotorBtn.innerText = 'Motor en Marcha...';
            elements.toggleMotorBtn.disabled = true;
        } else {
            elements.statusText.innerText = 'Detenido';
            elements.statusBadge.classList.remove('active');
            elements.toggleMotorBtn.innerText = 'Iniciar Motor';
            elements.toggleMotorBtn.disabled = false;
        }
    } catch (err) {
        console.error('Error fetching metrics:', err);
    }
}

// ─────────────────────────────────────────────────────────
// GESTIÓN DE PROMPTS
// ─────────────────────────────────────────────────────────
async function loadPrompts() {
    try {
        const resp = await fetch(`${API_BASE}/config/prompts`);
        const data = await resp.json();
        elements.promptApertura.value = data.apertura;
        elements.promptCierre.value = data.cierre;
    } catch (err) {
        console.error('Error loading prompts:', err);
    }
}

async function savePrompts() {
    const btn = elements.savePromptsBtn;
    btn.innerText = 'Sincronizando...';
    btn.disabled = true;

    try {
        const resp = await fetch(`${API_BASE}/config/prompts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                apertura: elements.promptApertura.value,
                cierre: elements.promptCierre.value
            })
        });
        if (resp.ok) {
            showNotification('Estrategia actualizada correctamente.');
        } else {
            throw new Error('Error en la respuesta');
        }
    } catch (err) {
        showNotification('Error al guardar la estrategia.', 'error');
    } finally {
        btn.innerText = 'Sincronizar Estrategia';
        btn.disabled = false;
    }
}

// ─────────────────────────────────────────────────────────
// UI / TABS
// ─────────────────────────────────────────────────────────
function initTabs() {
    elements.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const tab = btn.getAttribute('data-tab');
            if (tab === 'apertura') {
                elements.aperturaWrap.style.display = 'block';
                elements.cierreWrap.style.display = 'none';
            } else {
                elements.aperturaWrap.style.display = 'none';
                elements.cierreWrap.style.display = 'block';
            }
        });
    });
}

function showNotification(msg, type = 'success') {
    // Simple alert for now, could be a toast in the future
    alert(msg);
}

// ─────────────────────────────────────────────────────────
// MOTOR CONTROL
// ─────────────────────────────────────────────────────────
async function toggleMotor() {
    try {
        await fetch(`${API_BASE}/motor/start`, { method: 'POST' });
        fetchMetrics();
    } catch (err) {
        alert('Error al iniciar el motor.');
    }
}

async function sendTestEmail() {
    const email = elements.testEmailInput.value.trim();
    if (!email) {
        alert('Por favor, ingresa un correo de prueba.');
        return;
    }

    elements.sendTestBtn.disabled = true;
    elements.sendTestBtn.innerText = 'Enviando...';

    try {
        const resp = await fetch(`${API_BASE}/motor/test_send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await resp.json();

        if (data.status === 'success') {
            alert('¡Correo de prueba enviado con éxito!');
        } else {
            alert('Error: ' + data.message);
        }
    } catch (err) {
        alert('Error de conexión con el servidor.');
    } finally {
        elements.sendTestBtn.disabled = false;
        elements.sendTestBtn.innerText = 'Enviar Prueba';
    }
}

// ─────────────────────────────────────────────────────────
// LOGS (SSE)
// ─────────────────────────────────────────────────────────
function initLogs() {
    const eventSource = new EventSource(`${API_BASE}/logs`);
    eventSource.onmessage = (event) => {
        const line = document.createElement('div');
        line.className = 'log-line';

        const logText = event.data;
        if (logText.includes('[ERROR]')) {
            line.classList.add('error');
        } else if (logText.includes('[INFO]')) {
            line.classList.add('info');
        } else if (logText.includes('───')) {
            line.classList.add('divider');
        }

        line.innerText = logText;
        elements.logContainer.appendChild(line);
        elements.logContainer.scrollTop = elements.logContainer.scrollHeight;
    };
}

// ─────────────────────────────────────────────────────────
// INICIO
// ─────────────────────────────────────────────────────────
elements.savePromptsBtn?.addEventListener('click', savePrompts);
elements.toggleMotorBtn.addEventListener('click', toggleMotor);
elements.sendTestBtn.addEventListener('click', sendTestEmail);

initTabs();
fetchMetrics();
loadPrompts();
initLogs();
setInterval(fetchMetrics, 15000);
