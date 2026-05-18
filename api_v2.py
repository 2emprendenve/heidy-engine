# -*- coding: utf-8 -*-
import sys

# =============================================================================
# api_v2.py — Backend FastAPI para el Micro SaaS 2 (V2.1 - Bridge Ready)
# José Rafael Bravo León | Panel de Control Web
# =============================================================================
import logging
import threading
import time
import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException
import requests
import random
import gspread
import urllib.parse
from google.oauth2.service_account import Credentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

import config
import main
import engine_v2
import metrics_v2

# Forzar recarga de .env al iniciar este script específico
load_dotenv(override=True)

# ─────────────────────────────────────────────────────────
# CONFIGURACIÓN DE LOGS PARA STREAMING
# ─────────────────────────────────────────────────────────
class QueueHandler(logging.Handler):
    def __init__(self, queue_limit=100):
        super().__init__()
        self.logs = []
        self.queue_limit = queue_limit

    def emit(self, record):
        msg = self.format(record)
        self.logs.append(msg)
        if len(self.logs) > self.queue_limit:
            self.logs.pop(0)

log_queue = QueueHandler()
log_queue.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
logging.getLogger().addHandler(log_queue)

# ─────────────────────────────────────────────────────────
# ESTADO DEL MOTOR
# ─────────────────────────────────────────────────────────
class MotorState:
    def __init__(self):
        self.active = False
        self.thread = None
        self.metrics_data = {
            "f1_enviados": 0, "f1_rebotes": 0, "f1_eliminados": 0, "f1_aperturas": 0,
            "f2_interes": 0, "f2_enviados": 0, "f2_aperturas": 0, "f2_vendidos": 0,
            "estado": "DETENIDO"
        }

state = MotorState()

# ─────────────────────────────────────────────────────────
# CACHE DE CONEXIÓN Y MÉTRICAS (Anti-Quota Exceeded)
# ─────────────────────────────────────────────────────────
class Cache:
    spreadsheet = None
    last_metrics_refresh = 0
    metrics_cache = {}
    CACHE_TTL = 20  # Segundos

def get_spreadsheet_cached():
    if not Cache.spreadsheet:
        creds = Credentials.from_service_account_file(
            config.GOOGLE_CREDS_JSON,
            scopes=["https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive.readonly"]
        )
        gc = gspread.authorize(creds)
        Cache.spreadsheet = gc.open_by_key(config.GOOGLE_SHEET_ID)
    return Cache.spreadsheet

def motor_worker():
    """Ejecuta el pipeline de main.py en un hilo."""
    global state
    try:
        state.active = True
        state.metrics_data["estado"] = "EJECUTANDO"
        
        # Saludo personalizado
        logging.info("──────────────────────────────────────────────────────────")
        logging.info("🌟 ¡Hola, José Rafael Bravo León! El Tigre está despertando.")
        logging.info("🚀 Iniciando motor en modo " + ("Auditoría" if config.AUDIT_MODE else "Directo") + "...")
        logging.info("──────────────────────────────────────────────────────────")

        # Conectar a la sheet para el proceso
        import engine_v2
        engine_v2.run_engine()
        
    except Exception as e:
        logging.error(f"Error en el motor: {e}")
    finally:
        state.active = False
        state.metrics_data["estado"] = "TERMINADO"

# ─────────────────────────────────────────────────────────
# APP FASTAPI
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cargar métricas iniciales al arrancar
    logging.info(f"🚀 Iniciando servidor. Usando Sheet ID: {config.GOOGLE_SHEET_ID}")
    logging.info(f"📂 Archivo de credenciales: {config.GOOGLE_CREDS_JSON}")
    try:
        spreadsheet = get_spreadsheet_cached()
        metrics = metrics_v2.MetricsLogger(spreadsheet)
        state.metrics_data.update(metrics.get_summary())
    except Exception as e:
        logging.error(f"❌ Error inicial de conexión: {e}")
    yield

app = FastAPI(lifespan=lifespan, title="Micro SaaS 2 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────
# FRONTEND ESTÁTICO
# ─────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/api/metrics")
async def get_metrics():
    """Devuelve las métricas actuales con sistema de cache para evitar 429."""
    now = time.time()
    
    # Si la cache es reciente, devolvemos lo que tenemos
    if (now - Cache.last_metrics_refresh) < Cache.CACHE_TTL:
        return {**state.metrics_data, "active": state.active}

    try:
        spreadsheet = get_spreadsheet_cached()
        metrics = metrics_v2.MetricsLogger(spreadsheet)
        summary = metrics.get_summary()
        
        # Contar leads totales
        try:
            sheet = spreadsheet.worksheet(config.SHEET_TAB_LEADS)
            col_a = sheet.col_values(1)
            total_leads = len(col_a) - 1
            summary["total_leads"] = max(0, total_leads)
        except Exception as e_sheet:
            logging.error(f"❌ Error al contar leads: {e_sheet}")
            summary["total_leads"] = state.metrics_data.get("total_leads", 0)

        state.metrics_data.update(summary)
        Cache.last_metrics_refresh = now
        logging.info("🔄 Métricas refrescadas desde Google Sheets.")

    except Exception as e:
        logging.error(f"Error cargando métricas: {e}")
    
    return {**state.metrics_data, "active": state.active}

# ─────────────────────────────────────────────────────────
# TRACKING DE CLICS — /track reemplaza /si y /no
# ─────────────────────────────────────────────────────────

# Diccionario en memoria: token → datos del lead
# Se puebla cuando se genera el email en engine_v2
_token_registry: dict = {}

def register_token(token: str, lead_data: dict):
    """Registra el token de un lead para el seguimiento de clic."""
    _token_registry[token] = lead_data

@app.get("/health")
async def health_check():
    """
    Endpoint de salud para cron-job.org.
    Hacer ping a este endpoint cada 10 minutos mantiene el servidor
    despierto en Render Free Tier (evita cold-start de 60 segundos).
    """
    return {"status": "ok", "motor": "Heidy Engine v2", "active": state.active}


@app.get("/pixel")
async def track_open(token: str = "", background_tasks: BackgroundTasks = None):
    """
    Píxel invisible 1x1 para rastrear aperturas.
    Cambia el estado en Google Sheets a ABIERTO (o registra métrica).
    """
    lead = _token_registry.get(token)
    if lead:
        to_email = lead.get(config.COL_EMAIL, "")
        nombre   = (lead.get(config.COL_BUSINESS_NAME) or lead.get(config.COL_NOMBRE, "there"))
        fila     = lead.get(config.COL_FILA)
        logging.info(f"👁️ APERTURA REGISTRADA — {nombre} ({to_email}) abrió el correo.")
        
        # Opcionalmente marcar en Sheets:
        try:
            spreadsheet = get_spreadsheet_cached()
            sheet = spreadsheet.worksheet(config.SHEET_TAB_LEADS)
            if fila:
                from engine_v2 import mark_lead
                is_outbox = lead.get("_is_outbox", True)
                mark_lead(sheet, fila, "ABIERTO", is_outbox=is_outbox)
                
                # Métrica
                ml = metrics_v2.MetricsLogger(spreadsheet)
                ml.log("F1_APERTURA", lead, detalle="Apertura silenciosa por Píxel")
        except Exception as e:
            logging.error(f"   ✗ Error actualizando Sheet (Pixel): {e}")

    # Devolver un GIF transparente de 1x1 píxel
    pixel_data = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    from fastapi import Response
    return Response(content=pixel_data, media_type="image/gif")



@app.get("/track")
async def track_click(token: str = "", background_tasks: BackgroundTasks = None):
    """
    El prospecto hizo clic en el link del Correo 1.
    Flujo automático INSTANTÁNEO:
      1. Identifica al lead por token
      2. Envía Correo 2 con los 2 KPIs restantes (regalo prometido)
      3. Actualiza Google Sheets → CLICKED
      4. Redirige a dailypaywithheidy.com (landing de Heidy)
    El cliente no necesita hacer nada más. Un clic = regalo enviado.
    """
    lead = _token_registry.get(token)

    if not lead:
        logging.warning(f"⚠️ Token no encontrado en registry: {token}")
        # Aunque no tengamos el lead, igual mandamos a la landing
        return RedirectResponse(url="https://www.dailypaywithheidy.com/")

    to_email = lead.get(config.COL_EMAIL, "")
    nombre   = (lead.get(config.COL_BUSINESS_NAME)
                or lead.get(config.COL_NOMBRE, "there"))
    fila     = lead.get(config.COL_FILA)

    logging.info(f"🎯 CLIC REGISTRADO — {nombre} ({to_email}) abrió el link del Correo 1")

    # ── 1. Enviar Correo 2 con los 2 KPIs regalo ──────────────
    try:
        from listener_v2 import send_segundo_correo
        ok = send_segundo_correo(to_email, nombre, lead=lead)
        if ok:
            logging.info(f"   💌 Correo 2 (2 KPIs regalo) enviado → {to_email}")
        else:
            logging.error(f"   ✗ Falló el envío del Correo 2 a {to_email}")
    except Exception as e:
        logging.error(f"   ✗ Error enviando Correo 2: {e}")

    # ── 2. Actualizar Google Sheets → CLICKED ─────────────────
    try:
        spreadsheet = get_spreadsheet_cached()
        sheet = spreadsheet.worksheet(config.SHEET_TAB_LEADS)
        if fila:
            from engine_v2 import mark_lead
            is_outbox = lead.get("_is_outbox", True)
            mark_lead(sheet, fila, "CLICKED", is_outbox=is_outbox)
            logging.info(f"   ✅ Fila {fila} → CLICKED")
    except Exception as e:
        logging.error(f"   ✗ Error actualizando Sheet: {e}")

    # ── 3. Redirigir a la landing de Heidy ────────────────────
    return RedirectResponse(url="https://www.dailypaywithheidy.com/")


@app.get("/si")
async def boton_si_legacy(token: str = ""):
    """Redirige al /track para compatibilidad con emails viejos."""
    return RedirectResponse(url=f"/track?token={token}")


@app.get("/no")
async def boton_no_legacy(token: str = ""):
    """Leads que no quieren — simplemente redirigir sin acción."""
    lead = _token_registry.get(token)
    if lead:
        nombre   = (lead.get(config.COL_BUSINESS_NAME) or lead.get(config.COL_NOMBRE, ""))
        to_email = lead.get(config.COL_EMAIL, "")
        logging.info(f"   ➡️ {nombre} ({to_email}) — no accionó el link")
    return RedirectResponse(url="https://www.dailypaywithheidy.com/")

@app.post("/api/motor/start")
async def start_motor(background_tasks: BackgroundTasks):
    """Inicia el motor en segundo plano."""
    if state.active:
        return {"status": "error", "message": "El motor ya está en ejecución"}
    
    state.thread = threading.Thread(target=motor_worker, daemon=True)
    state.thread.start()
    return {"status": "success", "message": "Motor iniciado"}

@app.post("/api/motor/test_send")
async def test_send_email(data: dict):
    """Envía un email de prueba manual."""
    destinatario = data.get("email", "").strip()
    if not destinatario:
        return {"status": "error", "message": "Debes indicar un email"}

    logging.info(f"🧪 Enviando correo de prueba a: {destinatario}...")

    test_lead = {
        config.COL_NOMBRE:       "Empresa de Prueba",
        config.COL_BUSINESS_NAME:"Empresa de Prueba",
        config.COL_EMAIL:        destinatario,
        config.COL_NICHO:        "Negocio Local",
        config.COL_RATING:       "4.2",
        config.COL_RESEÑAS:      "28",
        config.COL_ZIP:          "00000",
        config.COL_ESTADO_GEO:   "TX",
        config.COL_ANALISIS:     "Prueba | Pixel: ❌ | Tag: ❌ | SSL: ✅",
        config.COL_PITCH:        "Blueprint de Prueba",
        config.COL_FRASE_EMPATIA:"Esta es una prueba del sistema.",
        config.COL_FILA:         None,
    }

    test_ai = {
        "Asunto_Email":      "Prueba de conexión | Sistema activo",
        "Intro_Equipo":      "Mi equipo revisó el sistema esta semana y quería verificar que todo funciona correctamente.",
        "Parrafo_Mercado":   "Este es un correo de prueba para verificar la conexión SMTP y el diseño del template.",
        "Parrafo_Emocional": "Si estás viendo esto, el sistema está funcionando correctamente.",
        "Pregunta_Cierre":   "¿El correo se ve bien en tu cliente de email?",
        "PD_Urgencia":       "Sistema Micro SaaS 2 operativo y listo para producción.",
        "url_si":            f"{config.SERVER_BASE_URL}/si?token=test",
        "url_no":            f"{config.SERVER_BASE_URL}/no?token=test"
    }

    try:
        ok = mailer_v2.send_email(test_lead, test_ai)
        if ok:
            return {"status": "success", "message": f"Prueba enviada a {destinatario}"}
        else:
            return {"status": "error", "message": "Error al enviar. Revisa los logs."}
    except Exception as e:
        logging.error(f"Error test_send: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/logs")
async def stream_logs():
    """Stream de logs usando SSE."""
    def log_generator():
        last_idx = 0
        while True:
            if last_idx < len(log_queue.logs):
                for i in range(last_idx, len(log_queue.logs)):
                    yield f"data: {log_queue.logs[i]}\n\n"
                last_idx = len(log_queue.logs)
            time.sleep(0.5)

    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.get("/api/config/prompts")
async def get_prompts():
    """Lee ambos archivos de prompts estratégicos."""
    try:
        cont_apertura = ""
        cont_cierre = ""
        if os.path.exists(config.PROMPT_APERTURA_FILE):
            with open(config.PROMPT_APERTURA_FILE, "r", encoding="utf-8") as f:
                cont_apertura = f.read()
        if os.path.exists(config.PROMPT_CIERRE_FILE):
            with open(config.PROMPT_CIERRE_FILE, "r", encoding="utf-8") as f:
                cont_cierre = f.read()
        return {
            "apertura": cont_apertura,
            "cierre": cont_cierre
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config/prompts")
async def save_prompts(data: dict):
    """Guarda los archivos de prompts estratégicos."""
    try:
        apertura = data.get("apertura")
        cierre = data.get("cierre")
        
        if apertura is not None:
            with open(config.PROMPT_APERTURA_FILE, "w", encoding="utf-8") as f:
                f.write(apertura)
        if cierre is not None:
            with open(config.PROMPT_CIERRE_FILE, "w", encoding="utf-8") as f:
                f.write(cierre)
                
        # Limpiar cache del engine
        engine_v2._prompt_cache["apertura"] = None
        engine_v2._prompt_cache["cierre"] = None
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ENDPOINTS PARA PANEL MINIMALISTA (Las 6 Opciones)
# ==========================================
import random
from engine_v2 import get_sheet, read_pending_leads, generate_batch
from mailer_v2 import send_email

@app.get("/api/action/leads_disponibles")
async def get_leads_disponibles():
    try:
        sheet = get_sheet()
        leads_all = read_pending_leads(sheet, n=50)
        leads_listos = [l for l in leads_all if str(l.get("ESTADO_CONTACTO", "")).upper() == "LISTO" or str(l.get("STATUS_ENVIO", "")).upper() == "PENDIENTE"]
        return {"status": "success", "total": len(leads_all), "listos": len(leads_listos), "leads": leads_all[:10]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/action/prueba_especifica")
async def action_prueba_especifica():
    # Opción 1 simplificada: toma el primer lead disponible
    try:
        sheet = get_sheet()
        leads = read_pending_leads(sheet, n=5)
        if not leads: return {"status": "error", "message": "No hay leads"}
        lead = leads[0]
        email_destino = os.getenv("TEST_EMAIL", "").strip()
        if email_destino: lead["EMAIL"] = email_destino
        results = generate_batch([lead])
        if results and not results[0].get("ai_error"):
            if send_email(lead, results[0]):
                return {"status": "success", "message": f"Prueba enviada para {lead.get('EMPRESA')} a {lead.get('EMAIL')}"}
        return {"status": "error", "message": "Error generando o enviando."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/action/auditoria")
async def action_auditoria():
    try:
        # Opción 3: Generar Excel (simplificado para UI, genera 10 para rapidez)
        sheet = get_sheet()
        leads = read_pending_leads(sheet, n=10)
        if not leads: return {"status": "error", "message": "No hay leads"}
        results = generate_batch(leads)
        return {"status": "success", "message": f"Auditoría generada en logs para {len(results)} leads."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/action/prueba_random")
async def action_prueba_random():
    try:
        sheet = get_sheet()
        leads = read_pending_leads(sheet, n=50)
        if not leads: return {"status": "error", "message": "No hay leads"}
        lead = random.choice(leads)
        email_destino = os.getenv("TEST_EMAIL", "").strip()
        lead["EMAIL"] = email_destino
        results = generate_batch([lead])
        if results and not results[0].get("ai_error"):
            if send_email(lead, results[0]):
                return {"status": "success", "message": f"Enviado lead random ({lead.get('EMPRESA')}) a {email_destino}"}
        return {"status": "error", "message": "Error enviando"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/action/autotest")
async def action_autotest():
    try:
        import urllib.parse
        import requests
        sheet = get_sheet()
        leads = read_pending_leads(sheet, n=50)
        if not leads: return {"status": "error", "message": "No hay leads"}
        lead = random.choice(leads)
        email_destino = os.getenv("TEST_EMAIL", "").strip()
        lead["EMAIL"] = email_destino
        results = generate_batch([lead])
        if results and not results[0].get("ai_error"):
            if send_email(lead, results[0]):
                nombre_corto = " ".join(lead.get("EMPRESA", "Lead").split()[:2])
                kpi4_val = str(lead.get("KPI_EFFICIENCY_GAP") or "")
                kpi5_val = str(lead.get("KPI_RIVALRY") or "")
                comp_val = str(lead.get("COMPETIDOR_NAME") or lead.get("COMPETITOR_NAME") or "")
                
                params = urllib.parse.urlencode({
                    "email": email_destino,
                    "name":  nombre_corto,
                    "kpi4":  kpi4_val[:200],
                    "kpi5":  kpi5_val[:200],
                    "comp":  comp_val[:80],
                })
                track_url = f"{config.SERVER_BASE_URL}/track?{params}"
                try:
                    requests.get(track_url, timeout=10)
                    return {"status": "success", "message": "Correo 1 enviado y clic simulado (Regalo disparado)."}
                except:
                    return {"status": "success", "message": "Correo 1 enviado. Falló simulación de clic."}
        return {"status": "error", "message": "Error enviando"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# DRAFT REVIEW SYSTEM — importado limpio
# ==========================================
from drafts_api import register_drafts_routes
register_drafts_routes(app, get_sheet, read_pending_leads, generate_batch, send_email)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
