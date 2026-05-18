# 🚀 Micro SaaS 2 — Motor de Correo Inteligente (Heidy Engine)

## ¿Qué hace este sistema?

Lee leads pre-calificados del Micro SaaS 1, genera un correo personalizado con Gemini usando los 5 KPIs de dolor del broker, lo envía, y marca el lead como procesado. Sin spam, sin duplicados, sin intervención humana.

---

## Arquitectura en 4 pasos

```
1. GET /get_outbox         → Micro SaaS 1 entrega leads PENDIENTES
2. Gemini genera correo    → usando KPI_CONTEXT de cada lead
3. SMTP envía el correo    → al EMAIL del broker
4. POST /mark_sent         → cierra el ciclo, previene re-envíos
```

---

## Fuente de datos: Micro SaaS 1

### Servidor Flask (ya corriendo en `sync_server.py`)
```
Base URL: http://localhost:5000   (o la URL configurada en .env SYNC_SERVER_URL)
Auth:     Header X-Sync-Token: {SYNC_API_TOKEN}   (opcional, solo si está en .env)
```

### Endpoint 1 — Obtener cola de trabajo

```
GET /get_outbox
Headers: X-Sync-Token: {token}

Response:
{
  "status": "ok",
  "total": 12,
  "leads": [
    {
      "FECHA_ALTA":        "2026-04-21 14:00:00",
      "SESSION_ID":        "A3B9F2C1",
      "NICHO":             "real_estate_agent_individual",
      "EMPRESA":           "John Broker LLC",
      "EMAIL":             "john@johnbroker.com",
      "CIUDAD":            "Miami",
      "ESTADO":            "FL",
      "MAPS_LINK":         "https://maps.google.com/...",
      "PRIORIDAD":         5,
      "KPI_LOCAL_SEARCH":  "Posición #9 en Maps — INVISIBLE ❌",
      "KPI_SHARE_OF_VOICE":"Miami Realty ocupa el 73% | John Broker solo el 27%",
      "KPI_SENTIMENT":     "Rating 4.3⭐ con 8 reseñas — velocidad: ESTANCADO",
      "KPI_EFFICIENCY_GAP":"Pagando presencia sin tráfico digital: sin Pixel ni Tag",
      "KPI_RIVALRY":       "Miami Realty tiene 45 reseñas (73% SoV). Gap: miami, luxury",
      "KPI_CONTEXT":       "Broker: John Broker LLC | ZIP: 33101 | Posición: #9 | ...",
      "FRASE_EMPATÍA":     "Veo el gran trabajo que haces en John Broker LLC...",
      "STATUS_ENVIO":      "PENDIENTE",
      "FECHA_ENVIO":       "",
      "RESPUESTA":         ""
    }
  ]
}
```

### Endpoint 2 — Marcar como enviado

```
POST /mark_sent
Headers: Content-Type: application/json
         X-Sync-Token: {token}

Body:
{
  "business_name": "John Broker LLC",
  "email":         "john@johnbroker.com",
  "respuesta":     ""   // dejar vacío al enviar, actualizar si hay tracking
}

Response:
{
  "status":         "ok",
  "marked_outbox":  1,
  "marked_memoria": 1,
  "fecha_envio":    "2026-04-21 14:05:33"
}
```

---

## Generación del correo con Gemini

### Modelo recomendado
```
gemini-1.5-flash  (velocidad + costo óptimo para batch)
```

### Prompt base (inyectar por lead)

```python
SYSTEM_PROMPT = """
Eres José Rafael Bravo León, consultor de marketing digital humanista.
Tu estilo: directo, empático, sin jerga técnica, basado en datos reales.
Escribes en inglés profesional americano.
Máximo 180 palabras. Sin emoji en el cuerpo. Asunto con máximo 8 palabras.
"""

USER_PROMPT = f"""
Genera un cold email para este broker de real estate.

DATOS DEL BROKER:
{lead['KPI_CONTEXT']}

ESTRUCTURA DEL CORREO:
1. Asunto: menciona el nombre del negocio + el dolor específico (no genérico)
2. Línea 1: frase de evidencia — demuestra que investigaste (usa KPI_LOCAL_SEARCH o KPI_RIVALRY)
3. Línea 2: consecuencia real — qué le está costando ese problema en dinero/clientes
4. Línea 3: propuesta — una sola acción concreta, no un listado de servicios
5. CTA: una pregunta de cierre suave (no "¿tienes 15 minutos?")

RESTRICCIONES:
- No usar "I noticed", "I came across", "I hope this finds you well"
- No inventar números que no estén en los datos
- Usar los datos del KPI_CONTEXT tal cual — no adornar
- El nombre del competidor DEBE aparecer si está disponible

Devuelve SOLO el correo en formato:
SUBJECT: [asunto]
BODY:
[cuerpo]
"""
```

### Parsear la respuesta de Gemini

```python
def parse_gemini_email(raw_text: str) -> dict:
    lines = raw_text.strip().split("\n")
    subject = ""
    body_lines = []
    in_body = False
    for line in lines:
        if line.startswith("SUBJECT:"):
            subject = line.replace("SUBJECT:", "").strip()
        elif line.strip() == "BODY:":
            in_body = True
        elif in_body:
            body_lines.append(line)
    return {
        "subject": subject,
        "body":    "\n".join(body_lines).strip()
    }
```

---

## Envío SMTP

### Variables de entorno requeridas (agregar al .env del proyecto)

```env
# Micro SaaS 2 — Email Engine
GMAIL_USER=heidy@example.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx    # App Password de Gmail (no la contraseña real)
GEMINI_API_KEY=AIza...
SYNC_SERVER_URL=http://localhost:5000
SYNC_API_TOKEN=                           # dejar vacío si no hay token configurado
RATE_LIMIT_SECONDS=90                     # segundos entre correos (respetar límites Gmail)
```

### Función de envío

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(to_email: str, subject: str, body: str,
               from_name: str = "Heidy") -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{from_name} <{GMAIL_USER}>"
    msg["To"]      = to_email

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())
    return True
```

---

## Loop principal del agente

```python
import time
import requests
from google import generativeai as genai

def run_email_engine():
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # 1. Obtener cola
    r = requests.get(f"{SYNC_SERVER_URL}/get_outbox",
                     headers={"X-Sync-Token": SYNC_API_TOKEN})
    leads = r.json().get("leads", [])
    print(f"📬 {len(leads)} leads pendientes")

    for lead in leads:
        email_to  = lead.get("EMAIL", "")
        biz_name  = lead.get("EMPRESA", "")

        if not email_to or "@" not in email_to:
            print(f"⚠️ Saltando {biz_name}: sin email válido")
            continue

        # 2. Generar correo con Gemini
        try:
            prompt   = USER_PROMPT.format(lead=lead)  # usa el template de arriba
            response = model.generate_content(
                [SYSTEM_PROMPT, prompt],
                generation_config={"temperature": 0.7, "max_output_tokens": 512}
            )
            email_data = parse_gemini_email(response.text)
        except Exception as e:
            print(f"❌ Gemini error para {biz_name}: {e}")
            continue

        if not email_data["subject"] or not email_data["body"]:
            print(f"⚠️ Gemini devolvió respuesta vacía para {biz_name}")
            continue

        # 3. Enviar
        try:
            send_email(to_email=email_to,
                       subject=email_data["subject"],
                       body=email_data["body"])
            print(f"✅ Enviado → {biz_name} ({email_to})")
        except Exception as e:
            print(f"❌ SMTP error para {biz_name}: {e}")
            continue

        # 4. Marcar como enviado
        requests.post(
            f"{SYNC_SERVER_URL}/mark_sent",
            json={"business_name": biz_name, "email": email_to},
            headers={"X-Sync-Token": SYNC_API_TOKEN}
        )

        # 5. Rate limiting (respetar límites de Gmail: ~500/día, ~20/hr)
        time.sleep(int(RATE_LIMIT_SECONDS))

if __name__ == "__main__":
    run_email_engine()
```

---

## Estructura de archivos sugerida

```
micro-saas-2/
├── .env                    ← variables de entorno (GMAIL, GEMINI, SYNC_SERVER_URL)
├── requirements.txt        ← google-generativeai, python-dotenv, requests
├── engine.py               ← loop principal (el código de arriba)
├── gemini_client.py        ← generate_email(lead) → {subject, body}
├── smtp_client.py          ← send_email(to, subject, body) → bool
├── scheduler.py            ← (opcional) cron/APScheduler para correr cada hora
└── README.md               ← este archivo
```

---

## requirements.txt

```
google-generativeai>=0.5.0
python-dotenv>=1.0.0
requests>=2.31.0
APScheduler>=3.10.0         # solo si usas scheduler automático
```

---

## Reglas de negocio críticas

| Regla | Razón |
|-------|-------|
| Solo enviar si `STATUS_ENVIO == "PENDIENTE"` | Evitar spam (ya lo filtra `/get_outbox`) |
| Solo enviar si `KPI_CONTEXT` no está vacío | Sin datos = Gemini alucina |
| Llamar `/mark_sent` SIEMPRE después de enviar | Aunque el correo falle, registrar el intento |
| `RATE_LIMIT_SECONDS >= 90` | Gmail bloquea si envías más de 20/hr desde una cuenta nueva |
| No inventar KPIs | El prompt prohíbe usar datos que no estén en `KPI_CONTEXT` |
| Máximo 500 correos/día por cuenta Gmail | Usar múltiples cuentas o SendGrid si se escala |

---

## Flujo de estado de un lead

```
1_MEMORIA_ETERNA.ESTADO_CONTACTO:   PENDIENTE → ENVIADO
OUTBOX_MICRO2.STATUS_ENVIO:       PENDIENTE → ENVIADO
OUTBOX_MICRO2.FECHA_ENVIO:        "" → "2026-04-21 14:05:33"
OUTBOX_MICRO2.RESPUESTA:          "" → ABIERTO / CLICK / INTERESADO (tracking futuro)
```

---

## Tracking de respuestas (fase 2)

Cuando el broker responde o hace click, actualizar el campo `RESPUESTA`:

```python
requests.post(f"{SYNC_SERVER_URL}/mark_sent", json={
    "business_name": biz_name,
    "email":         email_to,
    "respuesta":     "INTERESADO"   # o "ABIERTO", "CLICK", "NO_RESPONDE"
})
```

---

## Notas de arquitectura

- **Micro SaaS 1 y Micro SaaS 2 comparten el mismo Google Sheet** (`SHEET_ID` en config.py)
- **Micro SaaS 2 NUNCA escribe en `1_MEMORIA_ETERNA` directamente** — solo a través de `/mark_sent`
- **Micro SaaS 2 NUNCA lee `1_LIVE_EXTRACT`** — esa pestaña es interna de M1 y se borra en cada sesión. Lee de `1_OUTBOX_MICRO2`.
- **La única interfaz entre sistemas es:** `OUTBOX_MICRO2` (Sheets) + `/get_outbox` y `/mark_sent` (Flask)
- **`sync_server.py` debe estar corriendo** cuando Micro SaaS 2 ejecute (`lanzar_SYNC.bat`)
