# -*- coding: utf-8 -*-
import sys
import io

# Forzar encoding UTF-8 en Windows para evitar errores con emojis en consola
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# =============================================================================
# mailer_v2.py — Módulo de Envío Masivo Controlado
# Micro SaaS 2 | José Rafael Bravo León
# =============================================================================
"""
Responsabilidades:
  - Construir el cuerpo del email humanista (texto plano + HTML minimalista)
  - Enviar via smtplib con TLS
  - En DRY_RUN, simular el envío imprimiendo en consola
  - Pausas aleatorias entre envíos para proteger la reputación del dominio
"""

import smtplib
import random
import time
import json
import logging
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# REGISTRO DE MESSAGE-IDS (para detección In-Reply-To en IMAP)
# ─────────────────────────────────────────────────────────
def _load_message_log() -> dict:
    """Carga el registro de Message-IDs enviados desde el archivo JSON."""
    try:
        with open(config.MESSAGE_ID_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_message_log(log: dict) -> None:
    """Guarda el registro de Message-IDs en el archivo JSON."""
    with open(config.MESSAGE_ID_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def record_sent_id(message_id: str, lead: dict) -> None:
    """
    Persiste el Message-ID de un email enviado junto con datos del lead.
    El módulo IMAP usa estos IDs para detectar respuestas reales.
    """
    log = _load_message_log()
    log[message_id] = {
        "nombre":  lead.get(config.COL_NOMBRE, ""),
        "email":   lead.get(config.COL_EMAIL, ""),
        "nicho":   lead.get(config.COL_NICHO, ""),
        "fila":    lead.get(config.COL_FILA, ""),
    }
    _save_message_log(log)
    logger.debug(f"      📎 Message-ID guardado: {message_id}")


# ─────────────────────────────────────────────────────────
# 1. CONSTRUCCIÓN DEL CUERPO DEL EMAIL
# ─────────────────────────────────────────────────────────
_EMAIL_TEMPLATE_HTML = """\
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{
      font-family: Georgia, serif;
      max-width: 580px;
      margin: 40px auto;
      color: #1a1a1a;
      line-height: 1.75;
      background: #ffffff;
    }}
    p {{ margin: 0 0 20px; }}
    .intro {{ color: #444; font-size: 0.95em; font-style: italic; }}
    .separador {{
      border: none;
      border-top: 1px solid #e8e8e8;
      margin: 24px 0;
    }}
    .pregunta {{
      font-size: 1.05em;
      font-weight: bold;
      color: #1a1a1a;
      margin: 24px 0 20px;
    }}
    .cta-wrap {{
      margin: 28px 0;
    }}
    .btn-cta {{
      display: inline-block;
      background: #1a1a1a;
      color: #ffffff !important;
      text-decoration: none;
      padding: 14px 32px;
      border-radius: 6px;
      font-size: 1em;
      font-family: Georgia, serif;
      letter-spacing: 0.02em;
    }}
    .firma {{
      margin-top: 36px;
      padding-top: 20px;
      border-top: 1px solid #e8e8e8;
      font-size: 0.88em;
      color: #666;
      line-height: 1.6;
    }}
    .pd {{
      margin-top: 20px;
      font-size: 0.88em;
      color: #555;
      font-style: italic;
    }}
  </style>
</head>
<body>

  <p>Hola {nombre},</p>

  <p class="intro">{intro_equipo}</p>

  <hr class="separador">

  <p>{parrafo_mercado}</p>

  <p>{parrafo_emocional}</p>

  <p class="pregunta">{pregunta_cierre}</p>

  <div class="cta-wrap">
    <a class="btn-cta" href="{url_si}">See Your Free Market Report →</a>
  </div>

  <div class="firma">
    <strong>{from_name}</strong><br>
    Estratega de Crecimiento Digital
  </div>

  <p class="pd">P.D. — {pd_urgencia}</p>

</body>
</html>
"""

_EMAIL_TEMPLATE_TXT = """\
Hola {nombre},

{intro_equipo}

──────────────────────────────

{parrafo_mercado}

{parrafo_emocional}

{pregunta_cierre}

👉 See Your Free Market Report: {url_si}

──────────────────────────────
{from_name}
Estratega de Crecimiento Digital

P.D. — {pd_urgencia}
"""


def build_email_body(lead: dict, ai_result: dict) -> tuple[str, str]:
    """
    Construye el cuerpo del email usando los campos
    generados por Claude con los 8 KPIs.
    Retorna (plain_text, html_text).
    """
    nombre = (lead.get(config.COL_BUSINESS_NAME)
              or lead.get(config.COL_NOMBRE, "Emprendedor"))
    primer_nombre = nombre.split()[0] if nombre else "Emprendedor"

    # Campos generados por Claude (nuevos)
    intro_equipo      = ai_result.get("Intro_Equipo", "")
    parrafo_mercado   = ai_result.get("Parrafo_Mercado", "")
    parrafo_emocional = ai_result.get("Parrafo_Emocional", "")
    pregunta_cierre   = ai_result.get("Pregunta_Cierre", "")
    pd_urgencia       = ai_result.get("PD_Urgencia", "")
    url_si            = ai_result.get("url_si", config.SERVER_BASE_URL + "/si")
    url_no            = ai_result.get("url_no", config.SERVER_BASE_URL + "/no")

    # Limpiar P.D. duplicada antes de renderizar
    if pd_urgencia:
        # Eliminar prefijos duplicados
        pd_urgencia = pd_urgencia.replace("P.D. - P.D.", "P.D.")
        pd_urgencia = pd_urgencia.replace("P.D. — P.D.", "P.D.")
        pd_urgencia = pd_urgencia.replace("P.D.: P.D.:", "P.D.:")
        # Asegurar formato limpio
        if not pd_urgencia.startswith("P.D."):
            pd_urgencia = f"P.D. — {pd_urgencia}"

    context = dict(
        nombre=primer_nombre,
        intro_equipo=intro_equipo,
        parrafo_mercado=parrafo_mercado,
        parrafo_emocional=parrafo_emocional,
        pregunta_cierre=pregunta_cierre,
        pd_urgencia=pd_urgencia,
        url_si=url_si,
        url_no=url_no,
        from_name=config.FROM_NAME,
    )

    plain = _EMAIL_TEMPLATE_TXT.format(**context)
    html  = _EMAIL_TEMPLATE_HTML.format(**context)
    return plain, html


# ─────────────────────────────────────────────────────────
# 2. ENVÍO DE UN SOLO EMAIL
# ─────────────────────────────────────────────────────────
def send_email(lead: dict, ai_result: dict) -> bool:
    """
    Envía (o simula) el email para un lead.
    Retorna True si fue exitoso, False en caso de error.
    """
    to_email = lead.get(config.COL_EMAIL, "").strip()
    nombre   = lead.get(config.COL_NOMBRE, "Lead")
    subject  = ai_result.get("Asunto_Email", "Una idea para tu negocio")

    if not to_email:
        logger.warning(f"   ⚠️  Lead '{nombre}' sin email. Omitido.")
        return False

    plain_body, html_body = build_email_body(lead, ai_result)

    # ── Modo simulación ──────────────────────────────────
    if config.DRY_RUN:
        print("\n" + "═" * 60)
        print(f"  📧  [DRY-RUN] Email preparado — NO enviado")
        print(f"  Para   : {to_email}  ({nombre})")
        print(f"  Asunto : {subject}")
        print("─" * 60)
        print(plain_body[:400] + ("…" if len(plain_body) > 400 else ""))
        print("═" * 60)
        return True

    # ── Envío real via SMTP ──────────────────────────────
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"]      = subject
        msg["From"]         = f"{config.FROM_NAME} <{config.FROM_EMAIL}>"
        msg["To"]           = to_email
        msg["X-Mailer"]     = "MicroSaaS2-Motor"

        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body,  "html",  "utf-8"))

        import uuid as _uuid
        msg["Message-ID"]   = f"<{_uuid.uuid4()}@microsaas2.local>"

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASS)
            server.sendmail(config.FROM_EMAIL, [to_email], msg.as_string())

        logger.info(f"   ✉️  Enviado → {to_email} | Asunto: {subject}")
        # Registrar Message-ID para que listener_v2 detecte respuestas
        message_id = msg.get("Message-ID", "")
        if message_id:
            record_sent_id(message_id, lead)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("   ✗ Error de autenticación SMTP. Revisa usuario/contraseña.")
        return False
    except smtplib.SMTPException as exc:
        logger.error(f"   ✗ Error SMTP al enviar a {to_email}: {exc}")
        return False
    except Exception as exc:
        logger.error(f"   ✗ Error inesperado enviando a {to_email}: {exc}")
        return False


# ─────────────────────────────────────────────────────────
# 3. ENVÍO DE UN LOTE COMPLETO
# ─────────────────────────────────────────────────────────
def send_batch(batch_results: list[dict]) -> tuple[int, int]:
    """
    Envía un lote de emails respetando DAILY_EMAIL_LIMIT.
    Se detiene cuando se alcanza el límite diario.

    Returns:
        (enviados, errores) — contadores del lote.
    """
    enviados = 0
    errores  = 0

    for idx, item in enumerate(batch_results, start=1):
        # Saltar leads marcados por IA o con error
        if item.get("ai_error"):
            logger.warning(f"   ⚠️  Item {idx} omitido (error de IA previo).")
            errores += 1
            continue
        if item.get("ai_skipped"):
            logger.info(f"   ⏭️  Item {idx} omitido (SALTAR_LEAD).")
            continue

        # ─ Control de límite diario de 50 emails ────────────────
        if enviados >= config.DAILY_EMAIL_LIMIT:
            logger.warning(
                f"   🛑 Límite diario alcanzado ({config.DAILY_EMAIL_LIMIT} emails). "
                "Deteniendo lote. Los leads restantes mantendrán ESTADO=PENDIENTE."
            )
            break

        ok = send_email(item, item)
        if ok:
            enviados += 1
        else:
            errores += 1

        # Pausa anti-spam entre correos (excepto el último del día)
        if idx < len(batch_results) and enviados < config.DAILY_EMAIL_LIMIT:
            delay = random.uniform(config.EMAIL_DELAY_MIN, config.EMAIL_DELAY_MAX)
            logger.info(f"   ⏱️  Pausa anti-spam: {delay:.0f}s antes del siguiente email…")
            time.sleep(delay)

    logger.info(f"   📬 Lote completado — Enviados: {enviados} | Errores: {errores}")
    return enviados, errores
