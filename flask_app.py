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

app = Flask(__name__)

# ─── CONFIGURACIÓN (editar aquí directamente) ─────────────────────────────────
SMTP_USER   = "dailypaywithheidy@gmail.com"
SMTP_PASS   = "exyjspwspqduzgtr"
FROM_NAME   = "Heidy Nalley"
KAJABI_URL  = "https://www.dailypaywithheidy.com/"
LOG_FILE    = "clics_log.txt"


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

    # 1. Guardar el clic en el log
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] CLIC | Email: {email} | Name: {name} | Comp: {competitor}\n")
    except Exception as e:
        logging.error(f"Error guardando log: {e}")

    # 2. Enviar Correo 2 con los 2 KPIs regalo
    if email:
        _send_correo2(email, name, kpi4, kpi5, competitor)

    # 3. Redirigir a la landing de Heidy
    return redirect(KAJABI_URL, code=302)


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
