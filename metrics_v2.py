# =============================================================================
# metrics_v2.py — Módulo de Log y Métricas en Google Sheets
# Micro SaaS 2 | José Rafael Bravo León
# =============================================================================
"""
Escribe cada evento del sistema en la pestaña 'Métricas' de la Google Sheet.
Columnas gestionadas:
  Timestamp | Evento | Lead_Email | Lead_Nombre | Nicho | Detalle

Además, mantiene un RESUMEN ACUMULADO en las primeras 4 filas:
  [Métrica]           [Valor]
  Emails Enviados     42
  Rebotes             3
  Respuestas SÍ       7
  Tasa de Respuesta   16.7%
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

import config

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# CONSTANTES DE LA HOJA DE MÉTRICAS
# ─────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────
# CONSTANTES DE LA HOJA DE MÉTRICAS (Estructura Comparativa)
# ─────────────────────────────────────────────────────────
METRICS_TAB   = "Métricas (2)"
SUMMARY_ROWS  = 7        # Cuadro de mando compacto 

# Índices de fila del resumen (Columnas: A=Label, B=Fase 1, C=Fase 2)
ROW_TITLE          = 1
ROW_SUBTITLE       = 2
ROW_MET_ENVIADOS   = 3
ROW_MET_APERTURAS  = 4
ROW_MET_NEGATIVOS  = 5    # Rebotes (F1) / Eliminados (F2)
ROW_MET_EXITO      = 6    # Interés (F1 -> F2) / Vendido (F2 -> $)
ROW_MET_TASA       = 7

# Columnas del log de eventos (empiezan en la fila SUMMARY_ROWS + 3)
LOG_HEADERS = ["Timestamp", "Evento", "Lead_Email", "Lead_Nombre", "Nicho", "Detalle"]

# Eventos mapeados
EVT_F1_ENVIADO     = "F1_ENVIADO"
EVT_F1_REBOTE      = "F1_REBOTE"
EVT_F1_ELIMINADO   = "F1_ELIMINADO"
EVT_F1_APERTURA    = "F1_APERTURA"
EVT_F2_INTERES     = "F2_INTERES"
EVT_F2_ENVIADO     = "F2_ENVIADO_CIERRE"
EVT_F2_APERTURA    = "F2_APERTURA_CIERRE"
EVT_F2_VENDIDO     = "F2_VENDIDO"
EVT_ERROR          = "ERROR"
EVT_SISTEMA        = "SISTEMA"
EVT_PRUEBA_EXITOSA = "PRUEBA_EXITOSA"


# ─────────────────────────────────────────────────────────
# INICIALIZAR LA HOJA SI NO EXISTE
# ─────────────────────────────────────────────────────────
def _get_or_create_tab(ss: gspread.Spreadsheet, tab_name: str, headers: list[str]) -> gspread.Worksheet:
    """Obtiene una pestaña o la crea con cabeceras si no existe."""
    try:
        return ss.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=tab_name, rows="1000", cols=str(len(headers)))
        ws.append_row(headers)
        logger.info(f"   ✓ Pestaña '{tab_name}' creada.")
        return ws


def _get_or_create_metrics_sheet(ss: gspread.Spreadsheet) -> gspread.Worksheet:
    """Obtiene o crea la pestaña 'Métricas' con la estructura base."""
    try:
        ws = ss.worksheet(METRICS_TAB)
        return ws
    except gspread.exceptions.WorksheetNotFound:
        logger.info(f"   📊 Creando pestaña '{METRICS_TAB}'…")
        ws = ss.add_worksheet(title=METRICS_TAB, rows=500, cols=10)
        _bootstrap_metrics_sheet(ws)
        return ws


def _bootstrap_metrics_sheet(ws: gspread.Worksheet) -> None:
    """Escribe la estructura inicial comparativa (Fase 1 vs Fase 2)."""
    ws.update("A1:C8", [
        ["PANEL DE CONTROL: ORQUESTADOR SENIOR", "", ""],
        ["KPI", "FASE 1: APERTURA (PAZ)", "FASE 2: CIERRE ($600)"],
        ["Emails Enviados", 0, 0],
        ["Aperturas",       0, 0],
        ["Descartados",     0, 0], # Rebotes (F1) / Sin Interés (F2)
        ["Logros",          0, 0], # Interés Positivo (F1) / Vendido (F2)
        ["Tasa Conversión", "0.0%", "0.0%"],
        ["Última Ejecución", _now(), ""],
    ])
    # Cabeceras del log de eventos
    ws.update(f"A{SUMMARY_ROWS + 3}:{_col_letter(len(LOG_HEADERS))}{SUMMARY_ROWS + 3}",
              [LOG_HEADERS])
    logger.info(f"   ✓ Pestaña '{METRICS_TAB}' inicializada con layout comparativo.")


def _col_letter(n: int) -> str:
    """Convierte número de columna a letra (1→A, 2→B, …)."""
    result = ""
    while n:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ─────────────────────────────────────────────────────────
# LEER / ESCRIBIR RESUMEN
# ─────────────────────────────────────────────────────────
def _read_summary(ws: gspread.Worksheet) -> dict:
    """Lee los contadores actuales del Panel."""
    try:
        data = ws.get("B3:C6") # Rango central de KPIs
        def val(r, c):
            try: return int(float(data[r][c]))
            except: return 0
        return {
            "f1_enviados":  val(0, 0), "f2_enviados": val(0, 1),
            "f1_aperturas": val(1, 0), "f2_aperturas": val(1, 1),
            "f1_rebotes":   val(2, 0), "f1_eliminados": val(2, 1), # Descartados
            "f2_interes":   val(3, 0), "f2_vendidos":   val(3, 1), # Logros
        }
    except Exception:
        return {
            "f1_enviados": 0, "f2_enviados": 0, "f1_aperturas": 0, "f2_aperturas": 0,
            "f1_rebotes": 0, "f1_eliminados": 0, "f2_interes": 0, "f2_vendidos": 0
        }


def _write_summary(ws: gspread.Worksheet, s: dict) -> None:
    """Actualiza los contadores del panel side-by-side."""
    t1 = f"{(s['f2_interes'] / s['f1_enviados'] * 100):.1f}%" if s['f1_enviados'] > 0 else "0.0%"
    t2 = f"{(s['f2_vendidos'] / s['f2_enviados'] * 100):.1f}%" if s['f2_enviados'] > 0 else "0.0%"
    
    ws.update("B3:C7", [
        [s["f1_enviados"], s["f2_enviados"]],
        [s["f1_aperturas"], s["f2_aperturas"]],
        [s["f1_rebotes"], s["f1_eliminados"]],
        [s["f2_interes"], s["f2_vendidos"]],
        [t1, t2]
    ])
    ws.update("B8", [[_now()]])


# ─────────────────────────────────────────────────────────
# API PRINCIPAL
# ─────────────────────────────────────────────────────────
class MetricsLogger:
    """
    Logger de métricas que persiste en Google Sheets.
    Uso:
        ml = MetricsLogger(spreadsheet)
        ml.log(EVT_ENVIADO, lead)
        ml.log(EVT_SI_IMAP, lead, detalle="Respuesta entusiasta")
    """

    def __init__(self, spreadsheet: gspread.Spreadsheet):
        self._ss  = spreadsheet
        self._ws  = _get_or_create_metrics_sheet(spreadsheet)
        
        # Pestañas de Memoria (2)
        self._ws_recibidos = _get_or_create_tab(
            spreadsheet, config.SHEET_TAB_RECIBIDOS, 
            ["Fecha", "Email", "Nombre", "Nicho", "Prioridad", "Estado"]
        )
        self._ws_infinita  = _get_or_create_tab(
            spreadsheet, config.SHEET_TAB_INFINITA, 
            LOG_HEADERS
        )
        
        self._summary = _read_summary(self._ws)
        logger.info(f"   📈 MetricsLogger listo | Resumen actual: {self._summary}")

    def log(
        self,
        evento: str,
        lead: Optional[dict] = None,
        detalle: str = "",
    ) -> None:
        """
        Registra un evento en el log y actualiza los contadores del resumen.
        """
        lead = lead or {}
        row = [
            _now(),
            evento,
            lead.get(config.COL_EMAIL, ""),
            lead.get(config.COL_NOMBRE, ""),
            lead.get(config.COL_NICHO, ""),
            detalle[:200],   # truncar detalle largo
        ]

        if config.DRY_RUN:
            logger.info(f"   [METRICS-DRY] {evento} | {lead.get(config.COL_NOMBRE, '')} | {detalle}")
            # En DRY_RUN actualizamos los contadores en memoria pero no en Sheet
            self._update_counters(evento)
            return

        try:
            # 1. Log en Métricas (2) - El monitor actual
            self._ws.append_row(row, value_input_option="USER_ENTERED")
            
            # 2. Log en Memoria Infinita (2) - El histórico acumulado
            self._ws_infinita.append_row(row, value_input_option="USER_ENTERED")
            
            # 3. Actualizar contadores en resumen
            self._update_counters(evento)
            _write_summary(self._ws, self._summary)
        except Exception as exc:
            logger.error(f"   ✗ Error escribiendo en Métricas/Memoria: {exc}")

    def log_reception(self, leads: list[dict]) -> None:
        """Archiva un lote de leads recién recibidos en MEMORIA_RECIBIDOS (2)."""
        if not leads: return
        rows = []
        fecha = _now()
        for l in leads:
            rows.append([
                fecha,
                l.get(config.COL_EMAIL, ""),
                l.get(config.COL_NOMBRE, ""),
                l.get(config.COL_NICHO, ""),
                l.get(config.COL_PRIORIDAD, ""),
                l.get(config.COL_ESTADO, "LISTO")
            ])
        try:
            self._ws_recibidos.append_rows(rows, value_input_option="USER_ENTERED")
            logger.info(f"   💾 {len(leads)} leads archivados en MEMORIA_RECIBIDOS (2).")
        except Exception as exc:
            logger.error(f"   ✗ Error archivando en MEMORIA_RECIBIDOS: {exc}")

    def _update_counters(self, evento: str) -> None:
        if evento == EVT_F1_ENVIADO:
            self._summary["f1_enviados"] += 1
        elif evento == EVT_F1_REBOTE:
            self._summary["f1_rebotes"] += 1
        elif evento == EVT_F1_ELIMINADO:
            self._summary["f1_eliminados"] += 1
        elif evento == EVT_F1_APERTURA:
            self._summary["f1_aperturas"] += 1
        elif evento == EVT_F2_INTERES:
            self._summary["f2_interes"] += 1
        elif evento == EVT_F2_ENVIADO:
            self._summary["f2_enviados"] += 1
        elif evento == EVT_F2_APERTURA:
            self._summary["f2_aperturas"] += 1
        elif evento == EVT_F2_VENDIDO:
            self._summary["f2_vendidos"] += 1

    def get_summary(self) -> dict:
        """Devuelve el resumen en memoria."""
        return dict(self._summary)

    def print_summary(self) -> None:
        """Imprime el resumen en consola."""
        s = self._summary
        f1_env = s["f1_enviados"]
        tasa = f"{(s['f2_vendidos'] / f1_env * 100):.1f}%" if f1_env > 0 else "0.0%"
        print("\n" + "═" * 50)
        print("  📊  RESUMEN DE MÉTRICAS (KPI ORQUESTADOR)")
        print("─" * 50)
        print(f"  F1 Enviados     : {f1_env}")
        print(f"  F1 Aperturas    : {s['f1_aperturas']}")
        print(f"  F2 Interesados  : {s['f2_interes']}")
        print(f"  F2 Vendidos     : {s['f2_vendidos']}")
        print(f"  Tasa de Éxito   : {tasa}")
        print("═" * 50)
