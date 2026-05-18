# =============================================================================
# config.py — Micro SaaS 2: Motor de Ventas Humanista
# Autor: José Rafael Bravo León
# Descripción: Configuración centralizada. Lee variables del archivo .env
# =============================================================================

import os
from pathlib import Path
from dotenv import load_dotenv

# Carga el archivo .env desde el mismo directorio que este script
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ─────────────────────────────────────────────────────────
# 1. API DE IA (Vertex AI / Gemini AI Studio)
# ─────────────────────────────────────────────────────────
GEMINI_KEY:     str = os.getenv("GEMINI_KEY", "")
GEMINI_MODEL:   str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
OPENROUTER_KEY: str = os.getenv("OPENROUTER_KEY", "")
DEEPSEEK_KEY:   str = os.getenv("DEEPSEEK_KEY", "")

# --- VERTEX AI CONFIG ---
VERTEX_PROJECT_ID: str = os.getenv("VERTEX_PROJECT_ID", "")
VERTEX_REGION:     str = os.getenv("VERTEX_REGION", "us-central1")
VERTEX_JSON:       str = os.getenv("VERTEX_JSON", "")
GEMINI_MODEL_VERTEX: str = os.getenv("GEMINI_MODEL_VERTEX", "gemini-1.5-flash-002")

# ─────────────────────────────────────────────────────────
# 2. GOOGLE SHEETS
# ─────────────────────────────────────────────────────────
GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_CREDS_JSON: str = os.getenv("GOOGLE_CREDS_JSON", str(BASE_DIR / "credentials.json"))
SHEET_TAB_LEADS: str = os.getenv("SHEET_TAB_LEADS", "1_OUTBOX_MICRO2")   # Bridge MS1 a MS2: Unicornio Blanco
SHEET_TAB_RECIBIDOS: str = "MEMORIA_RECIBIDOS (2)"
SHEET_TAB_INFINITA: str = "MEMORIA_INFINITA (2)"

# Nombres de columna esperados en la Google Sheet
# Nombres de columna detectados en tu Sheet Real (Base_Datos_Extractor_Unicornio)
# Nombres de columna detectados en tu Sheet Real (Base_Datos_Extractor_Unicornio)
# Nombres de columna esperados en la Google Sheet
# Mapeo exacto para 1_OUTBOX_MICRO2 (Micro-SaaS 1)
COL_NOMBRE       = "EMPRESA"
COL_EMAIL        = "EMAIL"
COL_NICHO        = "NICHO"
COL_DOLOR        = "ANÁLISIS_PSICOLÓGICO"
COL_PRIORIDAD    = "PRIORIDAD"
COL_ESTADO       = "HEIDY_STATUS"   # Nueva columna limpia para evitar duplicados
COL_APERTURA     = "APERTURA"
COL_PROPUESTA_1  = "PROPUESTA_1"
COL_PROPUESTA_2  = "PROPUESTA_2_ANTIGRAVITY"
COL_FILA         = "_fila"
COL_MODO         = "MODO"

# ── BRIDGE micro-saas-1 → micro-saas-2 ──────────────────────
COL_RATING        = "RATING"
COL_RESEÑAS       = "TOTAL_RESEÑAS"
COL_WEB           = "WEB"
COL_MAPS          = "MAPS_LINK"
COL_ZIP           = "ZIP_CODE"
COL_ESTADO_GEO    = "ESTADO_GEO"   # Ajustado para evitar colisión
COL_ANALISIS      = "ANÁLISIS_PSICOLÓGICO"
COL_PITCH         = "PITCH_STRATEGY"
COL_FRASE_EMPATIA = "FRASE_EMPATÍA"
COL_NICHO_REAL    = "NICHO"
COL_BUSINESS_NAME = "EMPRESA"   # Sincronizado con 1_OUTBOX_MICRO2

# Estados permitidos (Arquitectura Orquestador)
STATUS_READY              = "LISTO"
STATUS_FOR_APPROVAL       = "POR_APROBAR"
STATUS_SENT               = "ENVIADO"
STATUS_CLICKED            = "CLICKED"        # Lead hizo clic en el link del Correo 1
STATUS_INTERESTED         = "INTERESADO"     # Lead entró a la landing de Heidy
STATUS_PENDING_CLOSE      = "CIERRE_PENDIENTE"
STATUS_FOR_APPROVAL_CLOSE = "POR_APROBAR_CIERRE"
STATUS_SOLD               = "VENDIDO"
STATUS_ERROR_DATA         = "ERROR_DATA"
STATUS_PROCESSING         = "PROCESANDO"

# Modo Auditoría: Si es True, los leads LISTO pasan a POR_APROBAR en vez de enviarse.
AUDIT_MODE = True

# ── SERVIDOR PÚBLICO (para botón SI/NO en el correo) ─────────
# Cambiar por tu URL de Railway/Render cuando despliegues
SERVER_BASE_URL: str = os.getenv("SERVER_BASE_URL", "http://localhost:5000")

# ── COLUMNA DE PROPUESTA LEGACY (compatibilidad engine) ──────
COL_PROPUESTA = COL_PROPUESTA_1

# ─────────────────────────────────────────────────────────
# 3. SMTP — ENVÍO DE EMAILS SALIENTES
# ─────────────────────────────────────────────────────────
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")          # tu@gmail.com
SMTP_PASS: str = os.getenv("SMTP_PASS", "")          # App Password de Google
FROM_NAME: str = os.getenv("FROM_NAME", "Heidy Nalley")
FROM_EMAIL: str = os.getenv("FROM_EMAIL", SMTP_USER)

# ─────────────────────────────────────────────────────────
# 4. IMAP — ESCUCHA DE RESPUESTAS ENTRANTES
# ─────────────────────────────────────────────────────────
# El sistema guarda los Message-IDs de los emails enviados para detectar
# respuestas reales por header In-Reply-To (más preciso que buscar por asunto).
IMAP_HOST: str = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER: str = os.getenv("IMAP_USER", SMTP_USER)
IMAP_PASS: str = os.getenv("IMAP_PASS", SMTP_PASS)
LISTEN_INTERVAL_SEC: int = int(os.getenv("LISTEN_INTERVAL_SEC", "1800"))  # 30 min

# Archivo local donde se guardan los Message-IDs de correos enviados.
# El listener los usa para detectar respuestas reales (In-Reply-To).
MESSAGE_ID_LOG: str = os.getenv("MESSAGE_ID_LOG", str(BASE_DIR / "sent_message_ids.json"))

# Marcador de asunto (fallback si el archivo de IDs no existe aún)
PROPUESTA_SUBJECT_MARKER: str = os.getenv("PROPUESTA_SUBJECT_MARKER", "Propuesta")

# ─────────────────────────────────────────────────────────
# 5. IA LOCAL GRATIS (Ollama) para clasificar respuestas
# ─────────────────────────────────────────────────────────
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")  # Modelo local gratuito

# ─────────────────────────────────────────────────────────
# 6. MODO TEST (muestreo de 1 lead aleatorio + envío a TEST_EMAIL)
# ─────────────────────────────────────────────────────────
# Si TEST_EMAIL tiene valor, el script toma 1 lead al azar, genera
# su propuesta con IA y envía un correo de identificación a esta dirección.
# Solo consume tokens de IA para ese único lead.
TEST_EMAIL: str = os.getenv("TEST_EMAIL", "").strip()

# ─────────────────────────────────────────────────────────
# 7. PROMPTS ESTRATÉGICOS
# ─────────────────────────────────────────────────────────
# Rutas a los archivos de instrucciones tácticas.
PROMPT_APERTURA_FILE: str = os.getenv("PROMPT_APERTURA_FILE", str(BASE_DIR / "prompt_apertura.txt"))
PROMPT_CIERRE_FILE: str   = os.getenv("PROMPT_CIERRE_FILE", str(BASE_DIR / "prompt_cierre.txt"))
# Mantener compatibilidad si se usa el anterior
PROMPT_FILE: str = PROMPT_APERTURA_FILE

# ─────────────────────────────────────────────────────────
# 9. EMBUDO DE KAJABI (segundo correo)
# ─────────────────────────────────────────────────────────
# Cuando el listener detecta un 'SÍ', envía el prospecto a este enlace.
# Kajabi se encarga del resto del embudo (precio, pago, onboarding).
# Nunca se menciona el precio en ningún correo.
KAJABI_URL: str = os.getenv("KAJABI_URL", "")
KAJABI_OFFER_NAME: str = os.getenv("KAJABI_OFFER_NAME", "Blueprint de Escalabilidad")

# ─────────────────────────────────────────────────────────
# 10. MODO DE PRUEBA
# ─────────────────────────────────────────────────────────
DRY_RUN: bool = os.getenv("DRY_RUN", "true").strip().lower() in ("true", "1", "yes")

# ─────────────────────────────────────────────────────────
# 8. CONTROL DE LOTES, LÍMITE DIARIO Y RESILIENCIA
# ─────────────────────────────────────────────────────────
BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "10"))
MIN_PRIORITY: int = int(os.getenv("MIN_PRIORITY", "4"))
TPM_PAUSE_SEC: float = float(os.getenv("TPM_PAUSE_SEC", "15.0"))   # Pausa entre lotes
EMAIL_DELAY_MIN: float = float(os.getenv("EMAIL_DELAY_MIN", "60.0"))
EMAIL_DELAY_MAX: float = float(os.getenv("EMAIL_DELAY_MAX", "120.0"))
DAILY_EMAIL_LIMIT: int = int(os.getenv("DAILY_EMAIL_LIMIT", "50"))  # Máx emails por día

# ─────────────────────────────────────────────────────────
# 8. VALIDACIÓN AL IMPORTAR
# ─────────────────────────────────────────────────────────
def validate():
    """Verifica que las credenciales críticas estén configuradas."""
    errores = []
    if not GEMINI_KEY:
        errores.append("ANTHROPIC_API_KEY no configurada.")
    if not GOOGLE_SHEET_ID:
        errores.append("GOOGLE_SHEET_ID no configurada.")
    if not SMTP_USER or not SMTP_PASS:
        errores.append("SMTP_USER / SMTP_PASS no configuradas.")
    if errores and not DRY_RUN:
        raise EnvironmentError(
            "⛔ Errores de configuración (desactiva DRY_RUN solo con config completa):\n"
            + "\n".join(f"  • {e}" for e in errores)
        )
    elif errores:
        print("⚠️  [DRY_RUN] Configuración incompleta — modo simulación activo:")
        for e in errores:
            print(f"   • {e}")
