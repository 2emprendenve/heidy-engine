"""
patch_flask.py — Reemplaza _send_correo2 en flask_app.py con la Version V4.
Ejecutar en PythonAnywhere: python3 patch_flask.py
"""
FLASK_FILE = '/home/2emprenden/flask_app.py'

NEW_FUNC = (
    'def _send_correo2(to_email, nombre, kpi4, kpi5, competitor):\n'
    '    """Heidy Engine V4 - Correo 2: The Reveal + Bridge."""\n'
    '    from flask import request\n'
    '    primer_nombre = nombre.split()[0] if nombre else "there"\n'
    '    business_name = nombre if nombre else "your business"\n'
    '    ciudad        = request.args.get("ciudad", "your area").strip() or "your area"\n'
    '    nicho         = request.args.get("nicho", "local business").strip() or "local business"\n'
    '    kpi_sentiment = request.args.get("kpi_sentiment", "5-star reviews").strip()\n'
    '\n'
    '    asunto = f"Your 2 hidden indicators, {primer_nombre} - here they are"\n'
    '\n'
    '    html = (\n'
    '        \'<div style="font-family:Arial,sans-serif;color:#333;font-size:14px;max-width:600px;line-height:1.5;">\'\n'
    '        \'<div style="background:#f8f9fa;padding:15px;border-radius:8px;margin-bottom:15px;border:1px solid #eaeaea;">\'\n'
    '        f\'<b>Following Up - {business_name} in {ciudad}</b><br><br>\'\n'
    '        f\'A short while ago I sent 3 data points about your visibility for <b>{nicho} in {ciudad}</b>.\'\n'
    '        \' I promised to reveal the 2 indicators I held back. Here they are.\'\n'
    '        \'</div>\'\n'
    '\n'
    '        \'<div style="background:#f8f9fa;padding:15px;border-radius:8px;margin-bottom:15px;border:1px solid #eaeaea;">\'\n'
    '        \'<b>Indicator #4 - The invisible trail your visitors leave</b><br><br>\'\n'
    '        f\'Right now, when someone finds {business_name} through a local search, your website \'\n'
    '        \'<b>does not record that visit</b>. That means:\'\n'
    '        \'<ul style="margin-top:10px;">\'\n'
    '        "<li>You can\'t tell how many clients are actually coming from Google.</li>"\n'
    '        "<li>You can\'t follow up with them automatically.</li>"\n'
    "        '<li>You\\'re investing in visibility but flying blind on returns.</li>'\n"
    '        \'</ul>\'\n'
    "        '<i>You\\'ve got a front door, but no doorbell.</i>'\n"
    '        \'</div>\'\n'
    '\n'
    '        \'<div style="background:#f8f9fa;padding:15px;border-radius:8px;margin-bottom:15px;border:1px solid #eaeaea;">\'\n'
    '        \'<b>Indicator #5 - The "trusted business" tag Google is denying you</b><br><br>\'\n'
    '        f\'Most of your direct competitors in {ciudad} have activated basic technical signals that Google \'\n'
    '        \'<b>recognises and rewards</b> with higher local rankings. \'\n'
    '        f\'{business_name} has not enabled them yet. \'\n'
    '        f\'That is why, even with <b>{kpi_sentiment}</b>, you are being left out of the visible group.\'\n'
    '        \'</div>\'\n'
    '\n'
    '        \'<div style="background:#f8f9fa;padding:15px;border-radius:8px;margin-bottom:15px;border:1px solid #eaeaea;">\'\n'
    '        \'<b>The fix (and how this ties into a bigger opportunity)</b><br><br>\'\n'
    '        f\'I work with a step-by-step system that helps <b>{nicho}</b> owners:\'\n'
    '        \'<ul style="margin-top:10px;">\'\n'
    '        \'<li>Track exactly which searches bring in real clients.</li>\'\n'
    '        \'<li>Close technical gaps that push you down in Google Maps.</li>\'\n'
    '        \'<li>Turn a 5-star reputation into weekly calls - not just pretty reviews.</li>\'\n'
    '        \'</ul>\'\n'
    '        \'The full plan is already documented and ready. No jargon. No fluff.\'\n'
    '        \'</div>\'\n'
    '\n'
    '        \'<div style="background:#eee;border-radius:10px;width:100%;margin:20px 0 10px;">\'\n'
    '        \'<div style="background:#5cb85c;width:85%;color:white;padding:5px;border-radius:10px;\'\n'
    '        \'font-size:10px;text-align:center;font-weight:bold;">SOLUTION READY</div></div>\'\n'
    '\n'
    '        \'<p style="text-align:center;margin-top:20px;">\'\n'
    '        f\'<a href="{KAJABI_URL}" style="background-color:#28a745;color:white;padding:14px 20px;\'\n'
    '        \'border-radius:5px;text-decoration:none;font-weight:bold;display:inline-block;\'\n'
    '        \'width:90%;text-align:center;">YES, EXPLAIN THE FREE PLAN &rarr;</a>\'\n'
    '        \'</p>\'\n'
    '\n'
    '        \'<p style="margin-top:30px;font-size:12px;color:#777;">\'\n'
    '        \'Heidy Nalley<br>Data Analyst &amp; Market Strategist</p>\'\n'
    '        \'</div>\'\n'
    '    )\n'
    '\n'
    '    try:\n'
    '        msg = MIMEMultipart("alternative")\n'
    '        msg["Subject"] = asunto\n'
    '        msg["From"]    = f"{FROM_NAME} <{SMTP_USER}>"\n'
    '        msg["To"]      = to_email\n'
    '        msg.attach(MIMEText(html, "html", "utf-8"))\n'
    '        with smtplib.SMTP("smtp.gmail.com", 587) as srv:\n'
    '            srv.ehlo(); srv.starttls(); srv.login(SMTP_USER, SMTP_PASS)\n'
    '            srv.sendmail(SMTP_USER, to_email, msg.as_string())\n'
    '        logging.info(f"Correo 2 V4 enviado -> {to_email}")\n'
    '        return True\n'
    '    except Exception as e:\n'
    '        logging.error(f"Error Correo 2: {e}")\n'
    '        return False\n'
)

# Read file
with open(FLASK_FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find function boundaries
start_line = None
end_line = len(lines)
for i, line in enumerate(lines):
    if 'def _send_correo2(' in line:
        start_line = i
    elif start_line is not None and i > start_line + 1 and line.startswith('def '):
        end_line = i
        break

if start_line is None:
    print("ERROR: No se encontro _send_correo2 en el archivo.")
    exit(1)

print(f"Funcion encontrada: lineas {start_line+1} a {end_line}")

# Replace
new_lines = lines[:start_line] + [NEW_FUNC + '\n\n'] + lines[end_line:]

with open(FLASK_FILE, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("OK - flask_app.py actualizado con Correo 2 V4")
print(f"Lineas reemplazadas: {end_line - start_line} -> verificando sintaxis...")

import py_compile
try:
    py_compile.compile(FLASK_FILE, doraise=True)
    print("Sintaxis OK - listo para reload")
except py_compile.PyCompileError as e:
    print(f"ERROR de sintaxis: {e}")
