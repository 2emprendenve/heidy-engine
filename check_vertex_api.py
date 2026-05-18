"""
check_vertex_api.py - Verifica si Vertex AI API esta habilitada
usando la cuenta de servicio del JSON.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import config
import requests
from google.oauth2 import service_account
import google.auth.transport.requests

# Obtener token
creds = service_account.Credentials.from_service_account_file(
    config.VERTEX_JSON,
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
auth_req = google.auth.transport.requests.Request()
creds.refresh(auth_req)
token = creds.token

project = config.VERTEX_PROJECT_ID
region = config.VERTEX_REGION

print(f"Proyecto: {project}")
print(f"Region  : {region}")
print()

# 1. Verificar si Vertex AI API esta habilitada
url_check = f"https://serviceusage.googleapis.com/v1/projects/{project}/services/aiplatform.googleapis.com"
resp = requests.get(url_check, headers={"Authorization": f"Bearer {token}"})
data = resp.json()
state = data.get("state", "UNKNOWN")
print(f"Estado API Vertex AI (aiplatform.googleapis.com): {state}")

if state == "ENABLED":
    print("[OK] La API de Vertex AI SI esta habilitada.")
else:
    print("[FAIL] La API NO esta habilitada. Ve a:")
    print(f"  https://console.cloud.google.com/apis/library/aiplatform.googleapis.com?project={project}")
    print("  y presiona el boton 'Habilitar'")

# 2. Listar modelos disponibles en la region
print()
print("Buscando modelos disponibles en us-central1...")
url_models = f"https://{region}-aiplatform.googleapis.com/v1/projects/{project}/locations/{region}/publishers/google/models"
resp2 = requests.get(url_models, headers={"Authorization": f"Bearer {token}"})
if resp2.status_code == 200:
    models = resp2.json().get("publisherModels", [])
    gemini_models = [m.get("name","") for m in models if "gemini" in m.get("name","").lower()]
    print(f"Modelos Gemini disponibles ({len(gemini_models)}):")
    for m in gemini_models[:10]:
        print(f"  - {m.split('/')[-1]}")
else:
    print(f"Error al listar modelos: {resp2.status_code} — {resp2.text[:200]}")
