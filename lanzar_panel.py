"""
lanzar_panel.py - Arranca el panel Antigravity Mailer y abre el navegador.
Ejecutar con:  python lanzar_panel.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import subprocess
import time
import webbrowser
import urllib.request
import os

PORT = 5000
URL  = f"http://localhost:{PORT}"

print("=" * 50)
print("ANTIGRAVITY MAILER - PANEL DE CONTROL")
print("=" * 50)

# 1. Arrancar el servidor en background
print(f"\n[*] Iniciando servidor en puerto {PORT}...")
servidor = subprocess.Popen(
    [sys.executable, "api_v2.py"],
    cwd=os.path.dirname(os.path.abspath(__file__)),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

# 2. Esperar hasta que responda (max 20s)
ok = False
for i in range(20):
    time.sleep(1)
    try:
        urllib.request.urlopen(f"{URL}/health", timeout=2)
        ok = True
        break
    except Exception:
        sys.stdout.write(f"   esperando... ({i+1}s)\r")
        sys.stdout.flush()

print()

if not ok:
    print("[X] El servidor no arranco en 20 segundos.")
    print("    Intenta correr directamente:  python api_v2.py")
    servidor.kill()
    sys.exit(1)

# 3. Abrir navegador
print(f"[OK] Servidor activo en {URL}")
print("[>>] Abriendo panel en el navegador...")
webbrowser.open(URL)

print()
print("-" * 50)
print("FLUJO:")
print("  1. Guarda prompt_apertura.txt y prompt_cierre.txt (Ctrl+S)")
print("  2. Panel -> boton '3. Generar & Auditar'")
print("  3. Modal con 10 borradores -> boton 'Ver' (preview HTML)")
print("  4. Aprueba los que quieras -> 'Enviar Aprobados'")
print("-" * 50)
print("Presiona Ctrl+C aqui para detener el servidor.")
print()

# 4. Mostrar logs del servidor en tiempo real
try:
    for line in servidor.stdout:
        decoded = line.decode("utf-8", errors="replace")
        sys.stdout.write(decoded)
        sys.stdout.flush()
except KeyboardInterrupt:
    print("\n\n[STOP] Deteniendo servidor...")
    servidor.terminate()
    print("[OK] Servidor detenido. Hasta luego!")
