# =============================================================================
# engine_v2.py — Motor de IA con Mini-Lotes 10x10
# Micro SaaS 2 | José Rafael Bravo León
# =============================================================================
import sys
import io

# Configuración básica de logging
import logging
import json
import time
import requests
import os
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_FILE = "draft_cache.json"

def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

# Intentar reconfigurar stdout para UTF-8 en Windows de forma segura
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

"""
Responsabilidades:
  - Leer leads PENDIENTES de Google Sheets (PRIORIDAD >= MIN_PRIORITY)
  - Construir prompts humanistas orientados al dolor del prospecto
  - Llamar a Claude API en lotes de 10, recibir JSON con copy persuasivo
  - Actualizar ESTADO en Google Sheets (PROCESANDO / ENVIADO / ERROR)
  - Control de TPM: pausa automática entre lotes
"""


import gspread
from google.oauth2.service_account import Credentials

import config

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# SCOPES DE GOOGLE SHEETS
# ─────────────────────────────────────────────────────────
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ─────────────────────────────────────────────────────────
# 1. CONEXIÓN A GOOGLE SHEETS
# ─────────────────────────────────────────────────────────
def get_sheet() -> gspread.Worksheet:
    """Devuelve la pestaña de leads de la Google Sheet."""
    creds = Credentials.from_service_account_file(config.GOOGLE_CREDS_JSON, scopes=_SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(config.GOOGLE_SHEET_ID)
    return spreadsheet.worksheet(config.SHEET_TAB_LEADS)


# ─────────────────────────────────────────────────────────
# 2. LECTURA DE LEADS PENDIENTES
# ─────────────────────────────────────────────────────────
def read_pending_leads(sheet: gspread.Worksheet, n: int = None) -> list[dict]:
    """
    Lee la sheet y devuelve los próximos `n` leads donde:
      - Fase 1 (Apertura): ESTADO == 'LISTO'
      - Fase 2 (Cierre):   ESTADO == 'INTERESADO' o APERTURA == 'SI' (y no cerrado yet)
      - PRIORIDAD >= config.MIN_PRIORITY
    """
    if n is None:
        n = config.BATCH_SIZE

    # Usamos get_all_values() y construimos los dicts manualmente para evitar errores de headers duplicados/vacíos
    data = sheet.get_all_values()
    if not data:
        return []
    
    headers = data[0]
    all_rows = []
    for i, row in enumerate(data[1:], start=2):
        # Aseguramos que el dict tenga el mismo largo que los headers
        row_dict = {headers[j]: row[j] if j < len(row) else "" for j in range(len(headers))}
        all_rows.append(row_dict)
    
    # Detectar formato de la pestaña
    is_outbox = "STATUS_ENVIO" in headers
    col_estado = "STATUS_ENVIO" if is_outbox else config.COL_ESTADO
    
    pending = []

    for i, row in enumerate(all_rows, start=2):
        try:
            prioridad = int(row.get(config.COL_PRIORIDAD, 0))
        except (ValueError, TypeError):
            prioridad = 0

        estado = str(row.get(col_estado, "")).strip().upper()
        if not is_outbox and config.COL_ESTADO not in row and not estado:
            estado = config.STATUS_READY

        apertura = str(row.get(config.COL_APERTURA, "")).strip().upper()

        # Determinar Fase
        lead_phase = None
        modo = str(row.get(config.COL_MODO, "")).strip().upper()
        
        if is_outbox:
            if estado == "PENDIENTE":
                lead_phase = 1
            elif estado == "INTERESADO":
                lead_phase = 2
        else:
            # 1_OUTBOX_MICRO2: si no hay columna MODO es un lead NUEVO → siempre fase 1
            if config.COL_MODO not in headers:
                # Lista de estados que impiden volver a enviar el Correo 1
                estados_finales_f1 = ("ENVIADO", "CLICKED", "VENDIDO", "ERROR_DATA", config.STATUS_SENT, config.STATUS_SOLD, "SENT_P2", "CIERRE_PENDIENTE")
                ya_enviado = estado in estados_finales_f1
                if not ya_enviado:
                    lead_phase = 1  # Correo 1 (Apertura)
            else:
                if not modo:
                    modo = "BLUEPRINT"
                if estado == config.STATUS_READY:
                    lead_phase = 2 if modo == "BLUEPRINT" else 1
                elif estado == config.STATUS_INTERESTED or apertura == "SI":
                    # Evitar duplicados en Fase 2: si ya se envió el cierre o está vendido/aprobación, saltar
                    estados_finales_f2 = (config.STATUS_PENDING_CLOSE, config.STATUS_FOR_APPROVAL_CLOSE, config.STATUS_SOLD, "SENT_P2", "CIERRE_PENDIENTE")
                    if estado not in estados_finales_f2:
                        lead_phase = 2

        if lead_phase and prioridad >= config.MIN_PRIORITY:
            lead = dict(row)
            lead[config.COL_FILA] = i
            lead["_phase"] = lead_phase
            lead["_is_outbox"] = is_outbox
            pending.append(lead)

        if len(pending) >= n:
            break

    logger.info(f"📋 Leads detectados para proceso: {len(pending)}")
    return pending


# ─────────────────────────────────────────────────────────
# 3. ACTUALIZAR ESTADO EN GOOGLE SHEETS
# ─────────────────────────────────────────────────────────
def mark_lead(sheet: gspread.Worksheet, fila: int, estado: str, is_outbox: bool = False) -> None:
    """Actualiza la celda ESTADO del lead en la fila dada."""
    try:
        headers = sheet.row_values(1)
        col_name = "STATUS_ENVIO" if is_outbox else config.COL_ESTADO
        col_idx = headers.index(col_name) + 1
        sheet.update_cell(fila, col_idx, estado)
        logger.debug(f"   ✓ Fila {fila} → {col_name} = {estado}")
    except Exception as exc:
        logger.error(f"   ✗ No se pudo actualizar {col_name} en fila {fila}: {exc}")


def mark_lead_sent(sheet: gspread.Worksheet, lead: dict) -> None:
    """
    Actualiza la fila del lead:
      - ESTADO = 'ENVIADO'
      - PROPUESTA_REDACTADA = el texto generado por IA
    """
    fila = lead.get(config.COL_FILA)
    if not fila: return
    is_outbox = lead.get("_is_outbox", False)

    try:
        from datetime import datetime
        headers = sheet.row_values(1)
        nuevo_estado = "ENVIADO"  # FIX #5: valor por defecto para evitar NameError en rama is_outbox
        
        if is_outbox:
            col_estado = headers.index("STATUS_ENVIO") + 1
            col_fecha = headers.index("FECHA_ENVIO") + 1
            cells_to_update = [
                gspread.Cell(row=fila, col=col_estado, value="ENVIADO"),
                gspread.Cell(row=fila, col=col_fecha,  value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            ]
        else:
            phase = lead.get("_phase", 1)
            # Para Fase 2 usamos un estado terminal específico para evitar bucles
            nuevo_estado = config.STATUS_SENT if phase == 1 else config.STATUS_PENDING_CLOSE
            
            col_estado = headers.index(config.COL_ESTADO) + 1
            col_prop = headers.index(config.COL_PROPUESTA_1) + 1
            propuesta = lead.get("Propuesta_Paz", lead.get("Propuesta_Blueprint", ""))
            
            cells_to_update = [
                gspread.Cell(row=fila, col=col_estado, value=nuevo_estado),
                gspread.Cell(row=fila, col=col_prop,   value=propuesta)
            ]
        
        sheet.update_cells(cells_to_update)
        logger.info(f"   ✅ Fila {fila} actualizada: {nuevo_estado}.")
    except Exception as exc:
        logger.error(f"   ✗ Error al marcar fila {fila} como enviado: {exc}")


def mark_lead_error_data(sheet: gspread.Worksheet, fila: int, razon: str, is_outbox: bool = False) -> None:
    """Marca el lead como ERROR_DATA indicando la razón."""
    try:
        headers = sheet.row_values(1)
        col_name = "STATUS_ENVIO" if is_outbox else config.COL_ESTADO
        col_estado = headers.index(col_name) + 1
        sheet.update_cell(fila, col_estado, config.STATUS_ERROR_DATA)
        logger.warning(f"   ⚠️ Fila {fila} → {config.STATUS_ERROR_DATA} ({razon})")
    except Exception as exc:
        logger.error(f"   ✗ No se pudo marcar ERROR_DATA en fila {fila}: {exc}")


def mark_lead_for_approval(sheet: gspread.Worksheet, lead: dict) -> None:
    """
    En Modo Auditoría:
      - Guarda la propuesta generada (Fase 1 o 2).
      - Estado = 'POR_APROBAR' (Fase 1) o 'POR_APROBAR_CIERRE' (Fase 2).
    """
    fila = lead.get(config.COL_FILA)
    if not fila: return

    phase = lead.get("_phase", 1)
    is_outbox = lead.get("_is_outbox", False)
    
    try:
        headers = sheet.row_values(1)
        col_name = "STATUS_ENVIO" if is_outbox else config.COL_ESTADO
        col_estado = headers.index(col_name) + 1
        
        nuevo_estado = config.STATUS_FOR_APPROVAL_CLOSE if phase == 2 else config.STATUS_FOR_APPROVAL
        propuesta = lead.get("Propuesta_Blueprint", lead.get("Propuesta_Paz", ""))
        
        cells_to_update = [
            gspread.Cell(row=fila, col=col_estado, value=nuevo_estado)
        ]
        
        if not is_outbox:
            col_prop_name = config.COL_PROPUESTA_2 if phase == 2 else config.COL_PROPUESTA_1
            if col_prop_name in headers:
                col_prop = headers.index(col_prop_name) + 1
                cells_to_update.append(gspread.Cell(row=fila, col=col_prop, value=propuesta))

        sheet.update_cells(cells_to_update)
        logger.info(f"   📋 Fila {fila} (Fase {phase}) -> {nuevo_estado}. Esperando revisión.")
    except Exception as exc:
        logger.error(f"   ✗ Error al marcar fila {fila} para aprobación: {exc}")


def mark_batch(sheet: gspread.Worksheet, leads: list[dict], estado: str) -> None:
    """Marca todos los leads de un lote con el mismo estado."""
    for lead in leads:
        fila = lead.get(config.COL_FILA)
        if fila:
            mark_lead(sheet, fila, estado)


# ─────────────────────────────────────────────────────────
# 4. CARGA DEL PROMPT ESTRATÉGICO EXTERNO
# ─────────────────────────────────────────────────────────
_prompt_cache: dict[str, str | None] = {
    "apertura": None,
    "cierre": None
}

def load_tactical_prompt(phase: int = 1) -> str:
    """Lee el prompt táctico correspondiente a la fase."""
    global _prompt_cache
    key = "apertura" if phase == 1 else "cierre"
    
    if _prompt_cache[key] is not None:
        return _prompt_cache[key]

    prompt_path = config.PROMPT_APERTURA_FILE if phase == 1 else config.PROMPT_CIERRE_FILE
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            _prompt_cache[key] = f.read().strip()
        logger.info(f"   ✅ Prompt táctico (Fase {phase}) cargado.")
    except FileNotFoundError:
        logger.warning(f"   ⚠️  {prompt_path} no encontrado. Respaldo activo.")
        if phase == 1:
            _prompt_cache[key] = "Eres Heidy Nalley. Usa estructura PAZ (Problema, Agitación, Zenit) para apertura."
        else:
            _prompt_cache[key] = "Eres Heidy Nalley. Cierra la venta con el Blueprint de Libertad Financiera de $600."
    
    return _prompt_cache[key]


# ─────────────────────────────────────────────────────────
# 5. CONSTRUCCIÓN DEL PROMPT POR LEAD
# ─────────────────────────────────────────────────────────
def build_prompt(lead: dict) -> str:
    """Ensambla el prompt completo con contexto rico del lead."""
    phase = lead.get("_phase", 1)
    sistema = load_tactical_prompt(phase)

    # ── Datos básicos ────────────────────────────────────────
    nombre        = (lead.get(config.COL_BUSINESS_NAME)
                     or lead.get(config.COL_NOMBRE, "Business"))
    nombre_corto  = " ".join(nombre.split()[:2])
    nicho         = (lead.get(config.COL_NICHO_REAL)
                     or lead.get(config.COL_NICHO, "local business"))
    # Filtrar placeholder del extractor — __AGENT_MODE__ no es un nicho real
    if not nicho or nicho.strip().startswith("__") or "AGENT_MODE" in nicho:
        # Intentar detectar el tipo desde el nombre de la empresa
        emp_lower = nombre.lower()
        if any(w in emp_lower for w in ["mortgage", "lending", "home loan", "lender"]):
            nicho = "Mortgage Broker"
        elif any(w in emp_lower for w in ["dental", "dentist"]):
            nicho = "Dentist"
        elif any(w in emp_lower for w in ["law", "attorney", "legal"]):
            nicho = "Law Firm"
        else:
            nicho = "local business"
    nicho_plural  = nicho + "s" if not nicho.lower().endswith("s") else nicho
    sistema = sistema.replace("{nicho}", nicho_plural)
    sistema = sistema.replace("{Servicio}", nicho)   # Variable dinámica del nuevo prompt_apertura

    # ── Mandato de Idioma ────────────────────────────────────
    idioma_mandato = "\n\nIMPORTANT: YOU MUST WRITE EVERYTHING (SUBJECT AND BODY) IN ENGLISH. DO NOT USE SPANISH. If you use Spanish words like 'Liberando', 'Tiempo', or 'Negocio', you are failing. WRITE IN ENGLISH."
    
    # Contexto ───────────────────────────────────────────────
    contexto = f"{idioma_mandato}\n\n"
    dolor         = lead.get(config.COL_DOLOR, "")
    email         = lead.get(config.COL_EMAIL, "")

    # ── Datos de mercado ────────────────────
    rating        = lead.get(config.COL_RATING, "N/D")
    reseñas       = lead.get(config.COL_RESEÑAS, "N/D")
    web           = lead.get(config.COL_WEB, "")
    zip_code      = lead.get(config.COL_ZIP, "")
    zip_display   = zip_code or "tu zona"
    estado_geo    = lead.get(config.COL_ESTADO_GEO, "")
    analisis      = lead.get(config.COL_ANALISIS, "")

    # ── Ciudad y competidor ────────────
    ciudad            = (lead.get("CIUDAD") or lead.get("PRIORIDAD") or estado_geo or "tu zona").strip()
    competidor_nombre  = (lead.get("COMPETIDOR_NAME") or "").strip()
    if not competidor_nombre and lead.get("KPI_CONTEXT"):
        import re
        match = re.search(r"Competidor:\s*([^|(\n]+)", lead.get("KPI_CONTEXT"), re.IGNORECASE)
        if match:
            competidor_nombre = match.group(1).strip()
    competidor_reseñas = (lead.get("COMPETIDOR_REVIEWS") or "").strip()
    
    sistema = sistema.replace("{ciudad}", ciudad)
    sistema = sistema.replace("{Ciudad}", ciudad)          # variante mayúscula (nuevo prompt)
    sistema = sistema.replace("{zip}", zip_display)
    sistema = sistema.replace("{Business_Name}", nombre)   # asunto del nuevo prompt_cierre
    kpi_sentiment_str = f"{rating}\u2605 / {reseñas} reviews"
    sistema = sistema.replace("{KPI_SENTIMENT}", kpi_sentiment_str)
    # {KPI_LOCAL_SEARCH} — ranking real del scraper o fallback descriptivo para 1_OUTBOX_MICRO2
    kpi_local_raw = (lead.get("KPI_LOCAL_SEARCH") or "").strip()
    if not kpi_local_raw:
        riesgo_txt = lead.get("RESEÑAS_SIN_RESPUESTA", "")
        kpi_local_raw = "not in Top 3" if ("Invisible" in riesgo_txt or not riesgo_txt) else "outside the Local Pack"
    sistema = sistema.replace("{KPI_LOCAL_SEARCH}", kpi_local_raw)

    # {KPI_SHARE_OF_VOICE} — datos del competidor dominante
    kpi_sov = (lead.get("KPI_SHARE_OF_VOICE") or "").strip()
    if not kpi_sov:
        # Construir desde datos del competidor si existen, o sintético
        if competidor_nombre:
            comp_reviews = competidor_reseñas or "100+"
            kpi_sov = f"{competidor_nombre}: {comp_reviews} reviews (dominating {ciudad} search)"
        else:
            kpi_sov = f"Top {nicho} in {ciudad}: 200+ reviews (outranking you in Maps)"
    sistema = sistema.replace("{KPI_SHARE_OF_VOICE}", kpi_sov)
    # {keyword_principal} = "nicho ciudad" (ej: "mortgage broker Dallas")
    sistema = sistema.replace("{keyword_principal}", f"{nicho} {ciudad}")

    # ── Token de seguimiento ─────────────────
    import hashlib
    import urllib.parse
    token = hashlib.md5(f"{email}{nombre}".encode()).hexdigest()[:12]

    # Parámetros para PythonAnywhere (no necesita token registry en memoria)
    kpi4_val        = lead.get("KPI_EFFICIENCY_GAP", "")
    kpi5_val        = lead.get("KPI_RIVALRY", "")
    comp_val        = lead.get("COMPETIDOR_NAME") or lead.get("COMPETITOR_NAME") or competidor_nombre or ""
    kpi_sent_val    = lead.get("KPI_SENTIMENT") or lead.get("RATING_DISPLAY") or f"{rating}★ / {reseñas} reviews"
    params = urllib.parse.urlencode({
        "email":         email,
        "name":          nombre_corto,
        "ciudad":        ciudad[:80],
        "nicho":         nicho[:80],
        "kpi_sentiment": kpi_sent_val[:100] if kpi_sent_val else "",
        "kpi4":          kpi4_val[:200] if kpi4_val else "",
        "kpi5":          kpi5_val[:200] if kpi5_val else "",
        "comp":          comp_val[:80]  if comp_val  else "",
    })
    url_track = f"{config.SERVER_BASE_URL}/track?{params}"
    url_si = url_track
    url_no = f"{config.SERVER_BASE_URL}/no?email={urllib.parse.quote(email)}"

    # Reemplazo directo en el prompt maestro
    sistema = sistema.replace("{url_si}", url_si)
    sistema = sistema.replace("{url_kajabi}", config.KAJABI_URL)  # CTA del correo de cierre

    is_outbox = lead.get("_is_outbox", False)

    if is_outbox:
        # Extraer los 5 KPIs específicos
        kpi_local = lead.get("KPI_LOCAL_SEARCH", "")
        kpi_share = lead.get("KPI_SHARE_OF_VOICE", "")
        kpi_sentiment = lead.get("KPI_SENTIMENT", "")
        kpi_efficiency = lead.get("KPI_EFFICIENCY_GAP", "")
        kpi_rivalry = lead.get("KPI_RIVALRY", "")
        
        kpi_text = ""
        if kpi_local or kpi_share:
            kpi_text = f"KPI_LOCAL_SEARCH: \"{kpi_local}\"\nKPI_SHARE_OF_VOICE: \"{kpi_share}\"\nKPI_SENTIMENT: \"{kpi_sentiment}\"\nKPI_EFFICIENCY_GAP: \"{kpi_efficiency}\"\nKPI_RIVALRY: \"{kpi_rivalry}\""
        else:
            kpi_text = lead.get("KPI_CONTEXT", "No context available.")

        lead_block = f"""
DATOS DEL LEAD (KPIs pre-calculados):
- Negocio: {nombre_corto}
- Nicho: {nicho} | Plural: {nicho_plural}
- Ciudad/Área: {ciudad}
- ZIP Code: {zip_display}
- url_si: {url_si}
- url_no: {url_no}
- token: {token}

CONTEXTO INTELIGENTE:
{kpi_text}

CRÍTICO: El correo es para {nicho_plural}. Usa los KPIs proporcionados para atacar el dolor del prospecto de manera precisa.
Genera el texto plano ahora. Sin texto adicional.
"""
    else:
        # ── Bloque de contexto estándar (1_OUTBOX_MICRO2) ────────────────────────
        lead_block = f"""
DATOS DEL LEAD:
- Negocio: {nombre_corto}
- Nicho: {nicho} | Plural: {nicho_plural}
- Ciudad: {ciudad}
- ZIP: {zip_display}
- Rating: {rating} | Reseñas: {reseñas}
- Competidor en ZIP: {competidor_nombre or "No disponible"}
- Reseñas del competidor: {competidor_reseñas or "No disponible"}
- url_si: {url_si}
- url_no: {url_no}
- token: {token}

CRÍTICO: El correo es para {nicho_plural} en {ciudad}.
Genera el texto plano ahora. Sin texto adicional.
"""
    return f"{sistema}\n\n{idioma_mandato}\n\n{lead_block}"


# ─────────────────────────────────────────────────────────
# 6. ESTIMACIÓN DE TOKENS
# ─────────────────────────────────────────────────────────
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ─────────────────────────────────────────────────────────
# 7. MOTOR DE IA — Gemini 1.5 Flash (primario) + OpenRouter (fallback)
# ─────────────────────────────────────────────────────────

def _parse_texto_plano(texto: str) -> dict:
    campos = {
        "Asunto_Email": "",
        "Intro_Equipo": "",
        "Parrafo_Mercado": "",
        "Parrafo_Emocional": "",
        "Pregunta_Cierre": "",
        "PD_Urgencia": "",
    }
    mapeo = {
        "SUBJECT:":    "Asunto_Email",
        "HOOK:":       "Intro_Equipo",
        "COMPETIDOR:": "Parrafo_Mercado",
        "GAP:":        "Parrafo_Emocional",
        "INJURY:":     "Parrafo_Emocional",
        "QUESTION:":   "Pregunta_Cierre",
        "SIGNATURE:":  "PD_Urgencia",
        "PD:":         "PD_Urgencia",
    }
    linea_actual = None
    for linea in texto.splitlines():
        linea = linea.strip()
        encontrado = False
        for etiqueta, campo in mapeo.items():
            if linea.upper().startswith(etiqueta):
                linea_actual = campo
                valor = linea[len(etiqueta):].strip()
                if valor:
                    campos[campo] = valor
                encontrado = True
                break
        if not encontrado and linea_actual and linea:
            campos[linea_actual] += " " + linea
    return campos


def _normalizar_respuesta(raw_text: str) -> Optional[dict]:
    """Convierte texto plano, JSON o HTML puro de la IA al dict interno del motor."""
    if not raw_text:
        return None

    texto_limpio = raw_text

    # Si el prompt devolvió la estructura HTML híbrida (SUBJECT: ... \n HTML)
    if "SUBJECT:" in raw_text.upper() and ("<DIV" in raw_text.upper() or "<P" in raw_text.upper() or "<A " in raw_text.upper()):
        lines = raw_text.strip().split('\n')
        asunto = "Market Insights"
        html_content = []
        for line in lines:
            if line.strip().upper().startswith("SUBJECT:"):
                asunto = line.split(":", 1)[1].strip()
            elif not line.strip().startswith("```"):
                html_content.append(line)
        return {
            "Asunto_Email": asunto,
            "Propuesta_HTML": "\n".join(html_content).strip()
        }

    # Limpiar bloques markdown para JSON
    if "```" in raw_text:
        for parte in raw_text.split("```"):
            parte = parte.strip().lstrip("json").strip()
            if parte.startswith("SUBJECT") or parte.startswith("{"):
                texto_limpio = parte
                break

    # Intentar parsear como JSON
    try:
        data = json.loads(texto_limpio)
        mapeo = {
            "SUBJECT":    "Asunto_Email",
            "HOOK":       "Intro_Equipo",
            "COMPETIDOR": "Parrafo_Mercado",
            "GAP":        "Parrafo_Emocional",
            "INJURY":     "Parrafo_Emocional",
            "QUESTION":   "Pregunta_Cierre",
            "PD":         "PD_Urgencia",
            "SIGNATURE":  "PD_Urgencia"
        }
        resultado = {}
        for k, v in data.items():
            clave_norm = mapeo.get(k.upper(), k)
            resultado[clave_norm] = v
            resultado[f"_raw_{k.upper()}"] = v
        return resultado
    except Exception:
        return _parse_texto_plano(raw_text)


def _call_gemini(prompt: str) -> Optional[dict]:
    """Motor PRIMARIO: Gemini 2.0 Flash — SDK google-genai v1.73."""
    if not config.GEMINI_KEY:
        logger.warning("   ⚠️  GEMINI_KEY no configurada — saltando Gemini.")
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GEMINI_KEY)
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=4000,   # suficiente para HTML completo con Bento
            )
        )
        raw_text = response.text.strip()
        logger.info(f"   🟦 [Gemini {config.GEMINI_MODEL}] Respuesta recibida ({len(raw_text)} chars)")
        return _normalizar_respuesta(raw_text)
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "quota" in err_str.lower() or "RESOURCE_EXHAUSTED" in err_str:
            logger.warning(f"   ⚠️  Gemini cuota/rate-limit — activando fallback OpenRouter.")
        elif "403" in err_str or "API_KEY" in err_str or "PERMISSION_DENIED" in err_str:
            logger.error(f"   ✗ Gemini API Key inválida o sin permisos: {err_str[:150]}")
        else:
            logger.error(f"   ✗ Gemini error: {err_str[:150]}")
        return None


def _call_openrouter(prompt: str) -> Optional[dict]:
    """Motor FALLBACK: OpenRouter (modelos gratuitos)."""
    models_to_try = [
        "google/gemma-3-27b-it:free",
        "google/gemma-3-12b-it:free",
        "google/gemma-3-4b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free"
    ]
    try:
        for model in models_to_try:
            try:
                time.sleep(2)
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.OPENROUTER_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://antigravity.app",
                        "X-Title": "Antigravity Mailer"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 3000   # suficiente para HTML de cierre completo
                    },
                    timeout=30
                )
                if resp.status_code == 429:
                    logger.warning(f"   Rate limit OpenRouter ({model}) — probando siguiente...")
                    continue
                if resp.status_code != 200:
                    logger.error(f"   Error OpenRouter ({model}) {resp.status_code}: {resp.text[:100]}")
                    continue

                raw_text = (resp.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                time.sleep(4)  # Respetar rate limit de API gratuita
                logger.info(f"   🟢 [OpenRouter/{model.split('/')[1]}] Respuesta recibida ({len(raw_text)} chars)")
                result = _normalizar_respuesta(raw_text)
                time.sleep(4)  # Pausa de seguridad
                return result

            except Exception as e:
                logger.error(f"   Error de conexión ({model}): {e}")
                continue

        logger.error("   ✗ Todos los modelos OpenRouter fallaron.")
        return None
    except Exception as e:
        logger.error(f"OpenRouter fallo crítico: {e}")
        return None


def _call_vertex(prompt: str) -> Optional[dict]:
    """Motor PREMIUM: Vertex AI (Google Cloud) — Usa los $300 de crédito."""
    if not config.VERTEX_PROJECT_ID or not config.VERTEX_JSON:
        return None
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        import google.auth
        from google.oauth2 import service_account

        # Autenticación con el JSON
        creds = service_account.Credentials.from_service_account_file(config.VERTEX_JSON)
        vertexai.init(project=config.VERTEX_PROJECT_ID, location=config.VERTEX_REGION, credentials=creds)
        
        model = GenerativeModel(config.GEMINI_MODEL_VERTEX)
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        logger.info(f"   🔥 [Vertex AI / {config.GEMINI_MODEL_VERTEX}] Respuesta recibida con CRÉDITOS.")
        return _normalizar_respuesta(raw_text)
    except Exception as e:
        logger.error(f"   ✗ Vertex AI error: {e}")
        return None


# Alias de compatibilidad con código legacy
_call_claude = _call_openrouter


def generate_batch(leads: list[dict], force_refresh: bool = False) -> list[dict]:
    results = []
    tokens_used = 0
    for i, lead in enumerate(leads, start=1):
        nombre = lead.get(config.COL_NOMBRE, f"Lead #{i}")
        email  = str(lead.get(config.COL_EMAIL, "")).strip()
        fila   = lead.get(config.COL_FILA)

        if not email:
            results.append({**lead, "ai_error": True, "error_type": "MISSING_EMAIL"})
            continue
            
        cache = _load_cache()
        if email in cache and not force_refresh:
            logger.info(f"   ⚡ [{i}/{len(leads)}] Recuperando borrador desde caché para: {email}")
            results.append({**lead, **cache[email]})
            continue
        
        logger.info(f"   🤖 [{i}/{len(leads)}] Procesando con IA: {nombre}")
        prompt = build_prompt(lead)
        tokens_used += estimate_tokens(prompt)

        # Generación real con IA (incluso en DRY_RUN, para poder previsualizar)

        # Validación de idioma: reintentar si el asunto está en español
        palabras_prohibidas = [
            "Liberando", "Tiempo", "Construyendo", "Negocio", "Energía", 
            "Futuro", "Financiero", "Base", "Dinero", "Rentable", "Escalar",
            "Tranquilidad", "Paz", "Control", "Vida", "Deseas", "Espero",
            "Respuesta", "Atentamente"
        ]
        intentos_idioma = 0
        while intentos_idioma < 5:
            # 1. Usar Gemini 2.5 Flash Lite directamente (API Studio)
            ai_result = _call_gemini(prompt)
            
            # 2. Fallback a Vertex si falla
            if ai_result is None:
                ai_result = _call_vertex(prompt)
            
            # 3. Fallback a OpenRouter
            if ai_result is None:
                logger.warning("   🔄 Todos los motores de Google fallaron — activando OpenRouter fallback...")
                ai_result = _call_openrouter(prompt)
            
            if ai_result is None:
                break
            
            asunto = str(ai_result.get("Asunto_Email", "")).strip()
            cuerpo = str(ai_result.get("Propuesta_Blueprint", "") or ai_result.get("Propuesta_Paz", "")).strip()
            
            # Chequeo agresivo: si el asunto o el inicio del cuerpo tienen palabras españolas comunes
            es_espanol = any(p.lower() in asunto.lower() for p in palabras_prohibidas)
            if not es_espanol and len(cuerpo) > 20:
                primeros_chars = cuerpo[:100].lower()
                es_espanol = any(p.lower() in primeros_chars for p in ["hola", "estimado", "recuerdo", "interesó"])

            if not es_espanol:
                break # Éxito, está en inglés (o al menos no tiene estas palabras)
            
            intentos_idioma += 1
            logger.warning(f"⚠️ Contenido en ESPAÑOL detectado. REGENERANDO EN INGLÉS... ({intentos_idioma}/5)")
        
        if ai_result is None or intentos_idioma >= 5:
            # Si falló el idioma tras todos los intentos, marcamos error
            if intentos_idioma >= 5:
                logger.error("❌ Falló validación de idioma tras 5 intentos. Abortando lead.")
            results.append({**lead, "ai_error": True, "error_type": "LANGUAGE_FAILURE"})
            continue
        
        if ai_result:
            cache[email] = ai_result
            _save_cache(cache)

        results.append({**lead, **ai_result})
        
        # Pausa minima entre peticiones (cuenta de pago — sin rate limit estricto)
        import time
        time.sleep(1)
        
    return results

def tpm_pause():
    logger.info(f"⏳ Pausa de {config.TPM_PAUSE_SEC}s entre lotes…")
    time.sleep(config.TPM_PAUSE_SEC)

def process_leads(sheet: gspread.Worksheet, leads: list[dict]):
    """Genera y envía correos para un lote de leads."""
    from mailer_v2 import send_batch
    
    # 0. Bloqueo Inmediato (Checkpoint para evitar duplicados)
    logger.info(f"   🔒 Bloqueando {len(leads)} leads en estado {config.STATUS_PROCESSING}...")
    for lead in leads:
        fila = lead.get(config.COL_FILA)
        is_outbox = lead.get("_is_outbox", False)
        if fila:
            mark_lead(sheet, fila, config.STATUS_PROCESSING, is_outbox)
            
    # 1. Generar contenido
    logger.info(f"   🤖 Generando contenido para {len(leads)} leads...")
    results = generate_batch(leads)
    
    # 2. Filtrar éxitos y errores
    to_send = []
    for item in results:
        fila = item.get(config.COL_FILA)
        is_outbox = item.get("_is_outbox", False)
        if item.get("error_type") or item.get("ai_error"):
            mark_lead_error_data(sheet, fila, item.get("error_type") or "AI_FAILURE", is_outbox=is_outbox)
        else:
            if config.AUDIT_MODE:
                mark_lead_for_approval(sheet, item)
            else:
                to_send.append(item)
    
    # 3. Enviar reales
    if to_send:
        logger.info(f"   📮 Enviando {len(to_send)} correos reales...")
        # Enviar uno a uno y marcar inmediatamente para evitar duplicados por interrupción
        from mailer_v2 import send_email
        for item in to_send:
            ok = send_email(item, item)
            if ok:
                mark_lead_sent(sheet, item)
            else:
                mark_lead_error_data(sheet, item.get(config.COL_FILA), "SEND_FAILURE", is_outbox=item.get("_is_outbox", False))

def run_engine(n: int = 50):
    """Función principal que procesa un número específico de leads pendientes."""
    sheet_ws = get_sheet()
    
    # Inicializar MetricsLogger para el mailer
    from mailer_v2 import get_metrics_logger
    get_metrics_logger(sheet_ws.spreadsheet)
    
    leads = read_pending_leads(sheet_ws, n=n)
    if not leads:
        logger.info("📭 No hay leads pendientes.")
        return
    process_leads(sheet_ws, leads)
