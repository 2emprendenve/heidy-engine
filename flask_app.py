# =============================================================================
# flask_app.py — Receptor de Clics para PythonAnywhere (Plan Gratuito)
# Heidy Engine v2 | 2emprenden.pythonanywhere.com
# =============================================================================
# Este archivo va en PythonAnywhere. No necesita Gemini.
# Solo hace 3 cosas cuando el prospecto hace clic:
#   1. Guarda el clic en clics_log.txt
#   2. Envía el Correo 2 con los 2 KPIs regalo (via Gmail SMTP)
#   3. Redirige al prospecto a dailypaywithheidy.com

import os
import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request, redirect
from dotenv import load_dotenv

# ── FIX CRÍTICO: Rutas absolutas para PythonAnywhere WSGI ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))  # Carga variables de entorno desde .env si existe

app = Flask(__name__)

try:
    import gspread
    from google.oauth2.service_account import Credentials
    _GSPREAD_OK = True
except ImportError:
    _GSPREAD_OK = False
    logging.warning("gspread no disponible — sincronización con Sheets desactivada.")

# ─── CONFIGURACIÓN (leer desde variables de entorno) ──────────────────────────
SMTP_USER   = os.getenv("SMTP_USER",   "dailypaywithheidy@gmail.com")
SMTP_PASS   = os.getenv("SMTP_PASS",   "")
FROM_NAME   = os.getenv("FROM_NAME",   "Heidy Nalley")
KAJABI_URL  = os.getenv("KAJABI_URL",  "https://www.dailypaywithheidy.com/")
LOG_FILE    = os.path.join(BASE_DIR, "clics_log.txt")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "19QaGyRQzL7vMHCTpRGGV6iD-U6jntMUBQ2huSZIOrtU")

def get_sheet(tab_name):
    if not _GSPREAD_OK:
        logging.warning("get_sheet: gspread no disponible, saltando.")
        return None
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        gc = gspread.authorize(creds)
        ss = gc.open_by_key(GOOGLE_SHEET_ID)
        return ss.worksheet(tab_name)
    except Exception as e:
        logging.error(f"Error conectando a sheets: {e}")
        return None


# ─── RUTA DE SALUD (para cron-job.org) ───────────────────────────────────────
@app.route("/")
def home():
    return "Servidor Heidy Activo 🦄", 200

@app.route("/health")
def health():
    return {"status": "ok", "motor": "Heidy Engine - PythonAnywhere"}, 200


# ─── RUTA PRINCIPAL: RECEPTOR DE CLICS ───────────────────────────────────────
@app.route("/track")
def track():
    """
    El prospecto hizo clic en el link del Correo 1.
    URL esperada: /track?email=EMAIL&name=NAME&kpi4=VALUE&kpi5=VALUE&comp=COMPETITOR
    """
    email      = request.args.get("email", "").strip()
    name       = request.args.get("name", "there").strip()
    kpi4       = request.args.get("kpi4", "").strip()
    kpi5       = request.args.get("kpi5", "").strip()
    competitor = request.args.get("comp", "your top competitor").strip()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Guardar el clic en el log y sincronizar con Google Sheets
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] CLIC | Email: {email} | Name: {name} | Comp: {competitor}\n")
            
        # Sincronizar con Google Sheets (Métricas (2), MEMORIA_INFINITA (2), y marcar en leads)
        try:
            ws_metrics = get_sheet("Métricas (2)")
            ws_infinita = get_sheet("MEMORIA_INFINITA (2)")
            row = [timestamp, "F2_INTERES", email, name, "Desconocido", f"Clic en CTA (PythonAnywhere) | Comp: {competitor}"]
            
            if ws_metrics:
                ws_metrics.append_row(row, value_input_option="USER_ENTERED")
                # Incrementar el contador de logros en F1 (cell B6)
                val = ws_metrics.acell('B6').value
                ws_metrics.update_acell('B6', int(val) + 1 if val and val.isdigit() else 1)
            
            if ws_infinita:
                ws_infinita.append_row(row, value_input_option="USER_ENTERED")
                
            # Marcar el lead como CLICKED en la pestaña de Leads ("1_OUTBOX_MICRO2")
            ws_leads = get_sheet("1_OUTBOX_MICRO2")
            if ws_leads and email:
                try:
                    headers = ws_leads.row_values(1)
                    if "EMAIL" in headers:
                        email_col = headers.index("EMAIL") + 1
                        status_col = None
                        if "HEIDY_STATUS" in headers:
                            status_col = headers.index("HEIDY_STATUS") + 1
                        elif "STATUS_ENVIO" in headers:
                            status_col = headers.index("STATUS_ENVIO") + 1
                            
                        if status_col:
                            for idx, val in enumerate(ws_leads.col_values(email_col), start=1):
                                if val.strip().lower() == email.lower():
                                    ws_leads.update_cell(idx, status_col, "CLICKED")
                                    logging.info(f"   ✓ Lead {email} marcado como CLICKED en la fila {idx}")
                                    break
                except Exception as sheet_lead_err:
                    logging.error(f"Error actualizando estado en leads: {sheet_lead_err}")
        except Exception as sheet_err:
            logging.error(f"Error sincronizando clic con Google Sheets: {sheet_err}")
    except Exception as e:
        logging.error(f"Error guardando log: {e}")

    # 2. Enviar Correo 2 con los 2 KPIs regalo
    if email:
        _send_correo2(email, name, kpi4, kpi5, competitor)

    # 3. Bridge Page (Página Puente) en lugar de redirección brusca
    bridge_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Report Sent!</title>
    <style>
        body {{ font-family: 'Georgia', serif; background-color: #f8f9fa; color: #1a1a1a; text-align: center; padding: 50px 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
        h1 {{ color: #2c3e50; font-size: 24px; margin-bottom: 10px; }}
        p {{ font-size: 16px; color: #555; line-height: 1.6; margin-bottom: 30px; }}
        .btn {{ display: inline-block; background-color: #1a1a2e; color: white !important; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; font-family: Arial, sans-serif; transition: background 0.3s; }}
        .btn:hover {{ background-color: #3b5bdb; }}
        .check-icon {{ font-size: 48px; margin-bottom: 20px; }}
    </style>
    <!-- Redirección automática después de 8 segundos -->
    <meta http-equiv="refresh" content="8;url={KAJABI_URL}">
</head>
<body>
    <div class="container">
        <div class="check-icon">📊</div>
        <h1>Your Report Is On Its Way!</h1>
        <p>The remaining <strong>2 key indicators</strong> have just been sent to <strong>{email}</strong>. Please check your inbox in the next few minutes.</p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        
        <p>While you wait, discover how other businesses are dominating their market with the <strong>2-Hour Workflow</strong> system.</p>
        <a href="{KAJABI_URL}" class="btn">Show Me The Path &rarr;</a>
        
        <p style="font-size: 13px; color: #aaa; margin-top: 25px;">You will be redirected automatically in 8 seconds...</p>
    </div>
</body>
</html>"""
    return bridge_html

@app.route("/pixel")
def pixel():
    """
    Píxel invisible 1x1 para rastrear aperturas.
    URL esperada: /pixel?email=EMAIL&name=NAME
    """
    email = request.args.get("email", "").strip()
    name = request.args.get("name", "there").strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Guardar en el log local de PythonAnywhere y Google Sheets
    try:
        if email:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] APERTURA | Email: {email} | Name: {name}\n")
            
            # Sincronizar con Google Sheets (Métricas (2), MEMORIA_INFINITA (2), y marcar ABIERTO en leads)
            try:
                ws_metrics = get_sheet("Métricas (2)")
                ws_infinita = get_sheet("MEMORIA_INFINITA (2)")
                row = [timestamp, "F1_APERTURA", email, name, "Desconocido", "Apertura silenciosa por píxel (PythonAnywhere)"]
                
                if ws_metrics:
                    ws_metrics.append_row(row, value_input_option="USER_ENTERED")
                    # Incrementar el contador de aperturas en F1
                    val = ws_metrics.acell('B4').value
                    ws_metrics.update_acell('B4', int(val) + 1 if val and val.isdigit() else 1)
                
                if ws_infinita:
                    ws_infinita.append_row(row, value_input_option="USER_ENTERED")

                # ── NUEVO: Marcar lead como ABIERTO en 1_OUTBOX_MICRO2 ──
                ws_leads = get_sheet("1_OUTBOX_MICRO2")
                if ws_leads:
                    try:
                        headers = ws_leads.row_values(1)
                        if "EMAIL" in headers:
                            email_col = headers.index("EMAIL") + 1
                            status_col = None
                            if "HEIDY_STATUS" in headers:
                                status_col = headers.index("HEIDY_STATUS") + 1
                            elif "STATUS_ENVIO" in headers:
                                status_col = headers.index("STATUS_ENVIO") + 1

                            if status_col:
                                for idx, val in enumerate(ws_leads.col_values(email_col), start=1):
                                    if val.strip().lower() == email.lower():
                                        # Solo marcar ABIERTO si el estado actual no es CLICKED o superior
                                        current = ws_leads.cell(idx, status_col).value or ""
                                        if current.upper() not in ("CLICKED", "INTERESADO", "VENDIDO"):
                                            ws_leads.update_cell(idx, status_col, "ABIERTO")
                                            logging.info(f"   ✓ Lead {email} marcado como ABIERTO en fila {idx}")
                                        break
                    except Exception as lead_err:
                        logging.error(f"Error marcando ABIERTO en leads: {lead_err}")

            except Exception as sheet_err:
                logging.error(f"Error subiendo a Sheets: {sheet_err}")

    except Exception as e:
        logging.error(f"Error guardando log de apertura: {e}")

    # Devolver un GIF transparente de 1x1 píxel
    from flask import Response
    pixel_data = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    return Response(pixel_data, mimetype="image/gif")


# ─── LEGADO: /si redirige a /track ───────────────────────────────────────────
@app.route("/si")
def si_legacy():
    return redirect("/track?" + request.query_string.decode(), code=302)

@app.route("/no")
def no_legacy():
    return redirect(KAJABI_URL, code=302)


# ─── ENVÍO DEL CORREO 2 ──────────────────────────────────────────────────────
def _send_correo2(to_email, nombre, kpi4, kpi5, competitor):
    """Envía el Correo 2 con los 2 KPIs restantes como regalo."""
    primer_nombre = nombre.split()[0] if nombre else "there"

    # Defaults si los KPIs vienen vacíos
    if not kpi4:
        kpi4 = ("Your current conversion rate is significantly below market average, "
                "meaning you're attracting traffic that your competitors are converting.")
    if not kpi5:
        kpi5 = ("Your top local competitor holds a dominant position in your category, "
                "with 3x more touchpoints across search and social channels.")

    asunto = f"Your 2 indicators, {primer_nombre} (as promised)"

    txt = f"""Hi {primer_nombre},

As I promised — here are the 2 indicators I kept for you.

📊 Indicator #4 — Efficiency Gap:
{kpi4}

📊 Indicator #5 — Competitive Rivalry Score:
{kpi5}

These two numbers tell me exactly how much ground you're losing
every month while {competitor} keeps capturing your clients.

The good news: there's a clear path to reverse this.
Businesses with your exact profile have gone from invisible
to consistently booked — without working more hours.

If you want to see how:
👉 {KAJABI_URL}

— Heidy Nalley

P.S. — No strings. You already took the first step by clicking.
The rest is just clarity.
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#ffffff;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:580px;margin:0 auto;padding:40px 24px;">
  <tr><td>
    <p style="font-size:16px;color:#1a1a1a;line-height:1.7;margin:0 0 20px;">Hi <strong>{primer_nombre}</strong>,</p>
    <p style="font-size:16px;color:#444;line-height:1.7;margin:0 0 24px;">As I promised &mdash; here are the <strong>2 indicators</strong> I kept for you.</p>

    <div style="background:#f4f6ff;border-left:4px solid #3b5bdb;padding:16px 20px;margin:0 0 16px;border-radius:4px;">
      <p style="font-size:11px;color:#3b5bdb;margin:0 0 6px;letter-spacing:0.08em;font-family:Arial,sans-serif;font-weight:bold;">INDICATOR #4 &mdash; EFFICIENCY GAP</p>
      <p style="font-size:15px;color:#1a1a1a;margin:0;line-height:1.6;">{kpi4}</p>
    </div>

    <div style="background:#fff4f4;border-left:4px solid #e03131;padding:16px 20px;margin:0 0 28px;border-radius:4px;">
      <p style="font-size:11px;color:#e03131;margin:0 0 6px;letter-spacing:0.08em;font-family:Arial,sans-serif;font-weight:bold;">INDICATOR #5 &mdash; COMPETITIVE RIVALRY SCORE</p>
      <p style="font-size:15px;color:#1a1a1a;margin:0;line-height:1.6;">{kpi5}</p>
    </div>

    <p style="font-size:16px;color:#1a1a1a;line-height:1.7;margin:0 0 20px;">These two numbers tell me exactly how much ground you&rsquo;re losing every month while <strong>{competitor}</strong> keeps capturing your clients.</p>
    <p style="font-size:16px;color:#1a1a1a;line-height:1.7;margin:0 0 28px;">The good news: there&rsquo;s a clear path to reverse this. Businesses with your exact profile have gone from invisible to consistently booked &mdash; without working more hours.</p>

    <p style="font-size:15px;color:#555;margin:0 0 16px;">If you want to see how:</p>
    <div style="text-align:center;margin:0 0 36px;">
      <a href="{KAJABI_URL}" style="background:#1a1a2e;color:#ffffff;padding:14px 36px;text-decoration:none;border-radius:8px;font-size:15px;font-weight:bold;display:inline-block;font-family:Arial,sans-serif;">Show Me The Path &rarr;</a>
    </div>

    <p style="font-size:16px;color:#1a1a1a;line-height:1.7;margin:0 0 8px;">&mdash; Heidy Nalley</p>
    <p style="font-size:13px;color:#999;line-height:1.6;margin:0;">P.S. &mdash; No strings. You already took the first step by clicking. The rest is just clarity.</p>
  </td></tr>
</table>
</body>
</html>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"]    = f"{FROM_NAME} <{SMTP_USER}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(txt,  "plain", "utf-8"))
        msg.attach(MIMEText(html, "html",  "utf-8"))

        with smtplib.SMTP("smtp.gmail.com", 587) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(SMTP_USER, SMTP_PASS)
            srv.sendmail(SMTP_USER, [to_email], msg.as_string())

        # Log éxito
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] CORREO2 ENVIADO → {to_email}\n")

    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] ERROR enviando Correo2 a {to_email}: {e}\n")


if __name__ == "__main__":
    app.run(debug=True)
