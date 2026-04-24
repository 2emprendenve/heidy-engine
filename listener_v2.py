# =============================================================================
# listener_v2.py — Módulo de Escucha IMAP + Clasificador IA Gratis + Auto-Reply
# Micro SaaS 2 | José Rafael Bravo León
# =============================================================================
"""
Ciclo de vida:
  1. Cada LISTEN_INTERVAL_SEC (30 min) conecta a Gmail via IMAP + SSL
  2. Busca correos NO LEÍDOS en toda la bandeja de entrada
  3. Filtra: solo procesa los que son RESPUESTA a un email que enviamos
     (detecta via header In-Reply-To o References contra sent_message_ids.json)
  4. Si no tiene ID registrado → fallback: busca el marcador en el asunto
  5. Clasifica el texto con Ollama (LLM local gratuito) → SÍ / NO / NEUTRO
  6. Si es SÍ: envía el "Segundo Correo" con el enlace de Kajabi
     (Kajabi maneja el precio, el pago y el onboarding. NUNCA se habla de precio aquí)
  7. Registra el evento en MetricsLogger + marca email como LEÍDO

Requisito gratuito:
  https://ollama.com → `ollama pull llama3.2`
  (Si Ollama no está disponible, usa clasificador de palabras clave como fallback)
"""

import imaplib
import email
import email.header
import json
import logging
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

import config
from metrics_v2 import (
    MetricsLogger, EVT_F2_INTERES, EVT_ERROR, EVT_F1_APERTURA, 
    EVT_F2_ENVIADO, EVT_F2_APERTURA, EVT_F2_VENDIDO, EVT_F1_ELIMINADO
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# PALABRAS CLAVE DE CLASIFICACIÓN (FALLBACK SIN OLLAMA)
# ─────────────────────────────────────────────────────────
_PALABRAS_SI = [
    "sí", "si", "claro", "me interesa", "interesado", "interesada",
    "cuéntame más", "cuentame", "quiero saber", "cómo funciona",
    "como funciona", "agendemos", "disponible", "perfecto", "adelante",
    "yes", "sure", "interested", "let's talk", "tell me more",
]
_PALABRAS_NO = [
    "no gracias", "no me interesa", "quita", "baja", "dar de baja",
    "unsubscribe", "remove", "stop", "not interested", "no thanks",
]


# ─────────────────────────────────────────────────────────
# 1. LECTURA DEL REGISTRO DE MESSAGE-IDS ENVIADOS
# ─────────────────────────────────────────────────────────
def _load_sent_ids() -> dict:
    """
    Carga el archivo sent_message_ids.json creado por mailer_v2.
    Retorna un dict: { "<message-id>": {"nombre": ..., "email": ..., ...} }
    """
    try:
        with open(config.MESSAGE_ID_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _find_lead_for_reply(msg: email.message.Message, sent_ids: dict) -> dict | None:
    """
    Busca en los headers In-Reply-To y References si el email entrante
    es respuesta a alguno de nuestros mensajes enviados.

    Si lo encuentra → devuelve el dict del lead (nombre, email, nicho, fila).
    Si no lo encuentra → devuelve None (se usará fallback por asunto).
    """
    in_reply_to = msg.get("In-Reply-To", "").strip()
    references  = msg.get("References", "").strip()

    # Reunir todos los IDs que menciona este correo
    candidate_ids = set()
    if in_reply_to:
        candidate_ids.add(in_reply_to)
    if references:
        # References puede tener múltiples IDs separados por espacios
        for ref_id in references.split():
            candidate_ids.add(ref_id.strip())

    for cid in candidate_ids:
        if cid in sent_ids:
            logger.debug(f"      🔗 In-Reply-To match: {cid}")
            return sent_ids[cid]

    return None  # no se encontró en nuestros enviados


# ─────────────────────────────────────────────────────────
# 2. CLASIFICADOR CON OLLAMA (IA LOCAL GRATUITA)
# ─────────────────────────────────────────────────────────
def classify_with_ollama(email_text: str) -> str:
    """
    Llama a Ollama (llama3.2 local) para determinar si la respuesta
    expresa interés positivo.
    Retorna: 'SI' | 'NO' | 'NEUTRO'
    """
    prompt = f"""Eres un asistente de ventas. Analiza esta respuesta de email y clasifícala.

RESPUESTA DEL PROSPECTO:
\"\"\"
{email_text[:800]}
\"\"\"

Responde ÚNICAMENTE con un JSON así (sin texto adicional):
{{"clasificacion": "SI"}}   ← si hay interés claro o voluntad de conversar
{{"clasificacion": "NO"}}   ← si rechaza o pide darse de baja
{{"clasificacion": "NEUTRO"}} ← si es ambiguo o una respuesta automática

Solo devuelve el JSON. Nada más."""

    try:
        resp = requests.post(
            config.OLLAMA_URL,
            json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("response", "").strip()
        parsed = json.loads(raw)
        clasificacion = parsed.get("clasificacion", "NEUTRO").upper()
        if clasificacion not in ("SI", "NO", "NEUTRO"):
            clasificacion = "NEUTRO"
        logger.info(f"   🧠 Ollama clasificó: {clasificacion}")
        return clasificacion

    except requests.exceptions.ConnectionError:
        logger.warning("   ⚠️  Ollama no disponible. Usando clasificador de palabras clave.")
        return _classify_keywords(email_text)
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning(f"   ⚠️  Error parsing Ollama: {exc}. Usando fallback.")
        return _classify_keywords(email_text)


def _classify_keywords(text: str) -> str:
    """Clasificador de palabras clave como fallback sin IA."""
    text_lower = text.lower()
    for palabra in _PALABRAS_NO:
        if palabra in text_lower:
            return "NO"
    for palabra in _PALABRAS_SI:
        if palabra in text_lower:
            return "SI"
    return "NEUTRO"


# ─────────────────────────────────────────────────────────
# 3. SEGUNDO CORREO — REGALO DE 2 KPIs (activado por clic en /track)
# ─────────────────────────────────────────────────────────
_SEGUNDO_CORREO_TXT = """
Hi {nombre},

As I promised — here are the 2 indicators I kept for you.

📊 Indicator #4 — Efficiency Gap:
{kpi_efficiency}

📊 Indicator #5 — Competitive Rivalry Score:
{kpi_rivalry}

These two numbers tell me exactly how much ground you're losing
every month while {competitor} keeps capturing your clients.

The good news: there's a clear path to reverse this.
Businesses with your exact profile have gone from invisible
to consistently booked — without working more hours.

If you want to see how:
👉 {kajabi_url}

— Heidy Nalley

P.S. — No strings. You already took the first step by clicking.
The rest is just clarity.
"""

_SEGUNDO_CORREO_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#ffffff;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0"
       style="max-width:580px;margin:0 auto;padding:40px 24px;">
  <tr><td>

    <p style="font-size:16px;color:#1a1a1a;line-height:1.7;margin:0 0 20px;">
      Hi <strong>{nombre}</strong>,
    </p>
    <p style="font-size:16px;color:#444;line-height:1.7;margin:0 0 24px;">
      As I promised &mdash; here are the <strong>2 indicators</strong> I kept for you.
    </p>

    <!-- KPI 4 -->
    <div style="background:#f4f6ff;border-left:4px solid #3b5bdb;
                padding:16px 20px;margin:0 0 16px;border-radius:4px;">
      <p style="font-size:11px;color:#3b5bdb;margin:0 0 6px;
                letter-spacing:0.08em;font-family:Arial,sans-serif;font-weight:bold;">
        INDICATOR #4 &mdash; EFFICIENCY GAP
      </p>
      <p style="font-size:15px;color:#1a1a1a;margin:0;line-height:1.6;">
        {kpi_efficiency}
      </p>
    </div>

    <!-- KPI 5 -->
    <div style="background:#fff4f4;border-left:4px solid #e03131;
                padding:16px 20px;margin:0 0 28px;border-radius:4px;">
      <p style="font-size:11px;color:#e03131;margin:0 0 6px;
                letter-spacing:0.08em;font-family:Arial,sans-serif;font-weight:bold;">
        INDICATOR #5 &mdash; COMPETITIVE RIVALRY SCORE
      </p>
      <p style="font-size:15px;color:#1a1a1a;margin:0;line-height:1.6;">
        {kpi_rivalry}
      </p>
    </div>

    <p style="font-size:16px;color:#1a1a1a;line-height:1.7;margin:0 0 20px;">
      These two numbers tell me exactly how much ground you&rsquo;re losing
      every month while <strong>{competitor}</strong> keeps capturing your clients.
    </p>

    <p style="font-size:16px;color:#1a1a1a;line-height:1.7;margin:0 0 28px;">
      The good news: there&rsquo;s a clear path to reverse this.
      Businesses with your exact profile have gone from invisible
      to consistently booked &mdash; without working more hours.
    </p>

    <p style="font-size:15px;color:#555;margin:0 0 16px;">If you want to see how:</p>
    <div style="text-align:center;margin:0 0 36px;">
      <a href="{kajabi_url}"
         style="background:#1a1a2e;color:#ffffff;padding:14px 36px;
                text-decoration:none;border-radius:8px;font-size:15px;
                font-weight:bold;display:inline-block;font-family:Arial,sans-serif;">
        Show Me The Path &rarr;
      </a>
    </div>

    <p style="font-size:16px;color:#1a1a1a;line-height:1.7;margin:0 0 8px;">
      &mdash; Heidy Nalley
    </p>
    <p style="font-size:13px;color:#999;line-height:1.6;margin:0;">
      P.S. &mdash; No strings. You already took the first step by clicking.
      The rest is just clarity.
    </p>

  </td></tr>
</table>
</body>
</html>
"""


def build_segundo_correo(to_email: str, nombre: str, lead: dict = None) -> MIMEMultipart:
    """
    Construye el Correo 2 con los 2 KPIs restantes como regalo.
    Extrae KPI_EFFICIENCY_GAP y KPI_RIVALRY del lead si están disponibles.
    """
    lead = lead or {}
    primer_nombre = nombre.split()[0] if nombre else "there"
    kajabi_url    = config.KAJABI_URL or "https://www.dailypaywithheidy.com/"

    kpi_efficiency = lead.get("KPI_EFFICIENCY_GAP") or (
        "Your current conversion rate is significantly below market average, "
        "meaning you're attracting traffic that your competitors are converting."
    )
    kpi_rivalry = lead.get("KPI_RIVALRY") or (
        "Your top local competitor holds a dominant position in your category, "
        "with 3x more touchpoints across search and social channels."
    )
    competitor = (lead.get("COMPETIDOR_NAME") or lead.get("COMPETITOR_NAME") or "your top competitor")

    ctx = dict(
        nombre=primer_nombre,
        kpi_efficiency=kpi_efficiency,
        kpi_rivalry=kpi_rivalry,
        competitor=competitor,
        kajabi_url=kajabi_url,
        from_name=config.FROM_NAME,
    )

    asunto = f"Your 2 indicators, {primer_nombre} (as promised)"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = f"{config.FROM_NAME} <{config.FROM_EMAIL}>"
    msg["To"]      = to_email

    msg.attach(MIMEText(_SEGUNDO_CORREO_TXT.format(**ctx), "plain", "utf-8"))
    msg.attach(MIMEText(_SEGUNDO_CORREO_HTML.format(**ctx), "html",  "utf-8"))
    return msg


def send_segundo_correo(to_email: str, nombre: str, lead: dict = None) -> bool:
    """Envía el Correo 2 con los 2 KPIs regalo. Se activa al clic en /track."""
    msg = build_segundo_correo(to_email, nombre, lead=lead)

    if config.DRY_RUN:
        print("\n" + "★" * 60)
        print(f"  💌  [DRY-RUN] Correo 2 (Regalo 2 KPIs)")
        print(f"  Para   : {to_email}  ({nombre})")
        print(f"  Asunto : {msg['Subject']}")
        print("★" * 60)
        return True

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(config.SMTP_USER, config.SMTP_PASS)
            srv.sendmail(config.FROM_EMAIL, [to_email], msg.as_string())
        logger.info(f"   💌 Correo 2 (2 KPIs regalo) enviado → {to_email}")
        return True
    except Exception as exc:
        logger.error(f"   ✗ Error enviando Correo 2 a {to_email}: {exc}")
        return False


# ─────────────────────────────────────────────────────────
# 4. PARSEO DE EMAIL IMAP
# ─────────────────────────────────────────────────────────
def _decode_header(value: str) -> str:
    """Decodifica cabeceras de email que pueden estar en base64."""
    parts = email.header.decode_header(value)
    decoded = []
    for fragment, encoding in parts:
        if isinstance(fragment, bytes):
            decoded.append(fragment.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded.append(fragment)
    return " ".join(decoded)


def _extract_body(msg: email.message.Message) -> str:
    """Extrae el cuerpo de texto del mensaje."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisposition = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in cdisposition:
                charset = part.get_content_charset() or "utf-8"
                body += part.get_payload(decode=True).decode(charset, errors="replace")
    else:
        charset = msg.get_content_charset() or "utf-8"
        body = msg.get_payload(decode=True).decode(charset, errors="replace")
    return body.strip()


# ─────────────────────────────────────────────────────────
# 5. CICLO DE ESCUCHA IMAP
# ─────────────────────────────────────────────────────────
def check_inbox_once(metrics: MetricsLogger) -> int:
    """
    Conecta al IMAP, busca no leídos, filtra respuestas reales a nuestras
    propuestas (usando In-Reply-To), clasifica y responde con enlace Kajabi.
    Retorna el número de respuestas procesadas.
    """
    processed = 0
    logger.info(f"📬 Conectando a IMAP ({config.IMAP_HOST})…")

    try:
        mail = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
        mail.login(config.IMAP_USER, config.IMAP_PASS)
        mail.select("INBOX")
    except imaplib.IMAP4.error as exc:
        logger.error(f"   ✗ Error de autenticación IMAP: {exc}")
        return 0

    # Cargar nuestros Message-IDs enviados
    sent_ids = _load_sent_ids()

    # Buscar TODOS los no leídos (el filtro real lo hacemos con In-Reply-To)
    _, data = mail.search(None, "UNSEEN")
    mail_ids = data[0].split()

    if not mail_ids:
        logger.info("   📭 No hay emails no leídos.")
        mail.logout()
        return 0

    logger.info(f"   📩 {len(mail_ids)} email(s) no leído(s) encontrado(s).")

    for num in mail_ids:
        try:
            _, msg_data = mail.fetch(num, "(RFC822)")
            raw_email  = msg_data[0][1]
            msg        = email.message_from_bytes(raw_email)

            from_addr  = _decode_header(msg.get("From", ""))
            subject    = _decode_header(msg.get("Subject", ""))
            body_text  = _extract_body(msg)

            # Extraer solo el email del campo From
            email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,}", from_addr)
            to_email = email_match.group(0) if email_match else from_addr

            # ── Filtro principal: In-Reply-To / References ─────────
            lead_info = _find_lead_for_reply(msg, sent_ids)

            if lead_info is None:
                # Fallback: marcar si el asunto contiene nuestro marcador
                if config.PROPUESTA_SUBJECT_MARKER.lower() not in subject.lower():
                    logger.debug(f"   ⏭️  Email ignorado (no es respuesta a propuesta): {subject[:60]}")
                    continue  # No es nuestro — marcar como leído pero no procesar
                # Es un posible reply por asunto (sin ID en log)
                lead_info = {
                    "nombre": from_addr.split("<")[0].strip() or "Prospecto",
                    "email":  to_email,
                    "nicho":  "desconocido",
                    "fila":   "",
                }
                logger.info(f"   ⚠️  Fallback por asunto (ID no en log): {subject[:60]}")
            else:
                logger.info(f"   ✅ Respuesta identificada via In-Reply-To: {to_email}")

            nombre = lead_info.get("nombre", "Prospecto")
            logger.info(f"   🔍 Clasificando respuesta de: {to_email}")

            clasificacion = classify_with_ollama(body_text)

            lead_dummy = {
                config.COL_EMAIL:  to_email,
                config.COL_NOMBRE: nombre,
                config.COL_NICHO:  lead_info.get("nicho", ""),
            }

            if clasificacion == "SI":
                logger.info(f"   🎯 INTERÉS POSITIVO — enviando enlace Kajabi a {to_email}")
                send_segundo_correo(to_email, nombre)
                metrics.log(
                    EVT_F2_INTERES,
                    lead_dummy,
                    detalle=f"Clasificación: {clasificacion} | Asunto: {subject[:80]}",
                )
                metrics.log(EVT_F2_ENVIADO, lead_dummy, detalle="Blueprint enviado via Auto-Reply")
            else:
                logger.info(f"   ➡️  Sin interés positivo ({clasificacion}) — no se auto-responde.")
                metrics.log(
                    EVT_F1_ELIMINADO,
                    lead_dummy,
                    detalle=f"Clasificación: {clasificacion} (No interesado) | Asunto: {subject[:80]}",
                )

            # Marcar como leído
            mail.store(num, "+FLAGS", "\\Seen")
            processed += 1

        except Exception as exc:
            logger.error(f"   ✗ Error procesando email {num}: {exc}")
            metrics.log(EVT_ERROR, detalle=str(exc)[:150])

    mail.logout()
    return processed


def start_listener_loop(metrics: MetricsLogger) -> None:
    """
    Loop infinito: comprueba la bandeja cada LISTEN_INTERVAL_SEC segundos.
    Diseñado para correr en un hilo separado desde main.py.
    """
    logger.info(
        f"👂 Listener IMAP iniciado — intervalo: "
        f"{config.LISTEN_INTERVAL_SEC}s ({config.LISTEN_INTERVAL_SEC // 60} min)"
    )
    while True:
        try:
            processed = check_inbox_once(metrics)
            logger.info(f"   ✓ Ciclo IMAP completado. Respuestas procesadas: {processed}")
        except Exception as exc:
            logger.error(f"   ✗ Error en ciclo IMAP: {exc}")
        logger.info(f"   💤 Próxima comprobación en {config.LISTEN_INTERVAL_SEC // 60} minutos…")
        time.sleep(config.LISTEN_INTERVAL_SEC)
