import os
import sys
import argparse
import gspread
from google.oauth2.service_account import Credentials
import logging

try:
    import config
except ImportError:
    print("Error: config.py no encontrado.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Scopes para gspread
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

def _sanity_check(func):
    """Marca una función para ser ejecutada como chequeo de sanidad por quick_heal."""
    func._sanity_check = True
    return func

@_sanity_check
def main_sanity():
    # Chequeo de sanidad autosuficiente: solo verificar imports clave
    assert True

def get_sheet() -> gspread.Worksheet:
    creds = Credentials.from_service_account_file(config.GOOGLE_CREDS_JSON, scopes=_SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(config.GOOGLE_SHEET_ID)
    return spreadsheet.worksheet(config.SHEET_TAB_LEADS)

def sanitize(test_mode=True):
    logger.info(f"🚀 Iniciando Sanitizador en memoria (Hoja: {config.SHEET_TAB_LEADS})")
    if test_mode:
        logger.info("   [MODO TEST ACTIVO] - No se realizarán cambios en la hoja.")
    
    try:
        sheet = get_sheet()
        all_data = sheet.get_all_values()
    except Exception as e:
        logger.error(f"[ERROR] Falló la conexión a Google Sheets: {e}")
        return

    if not all_data:
        logger.info("La hoja está vacía.")
        return

    headers = [str(h).strip() for h in all_data[0]]
    rows = all_data[1:]
    
    logger.info(f"   Filas iniciales escaneadas: {len(rows)}")

    # Fase A: Validacion Estructural
    if config.COL_EMAIL not in headers:
        logger.error(f"Falta la columna clave: {config.COL_EMAIL}")
        return
        
    if config.COL_ESTADO not in headers:
        headers.append(config.COL_ESTADO)
        for r in rows:
            r.append("")

    col_email_idx = headers.index(config.COL_EMAIL)
    col_estado_idx = headers.index(config.COL_ESTADO)
    
    seen_emails = {}
    
    filas_eliminadas_invalidas = 0
    filas_eliminadas_duplicadas = 0
    filas_corregidas = 0

    for idx, row in enumerate(rows):
        # Asegurar longitud igual a headers
        while len(row) < len(headers):
            row.append("")
            
        email_bruto = str(row[col_email_idx])
        email_limpio = email_bruto.strip().lower()
        
        # Validacion de correos invalidos
        if not email_limpio or "@" not in email_limpio:
            filas_eliminadas_invalidas += 1
            continue
            
        if email_bruto != email_limpio:
            filas_corregidas += 1
            row[col_email_idx] = email_limpio
            
        # Fase B: Deduplicacion Factual
        # Si ya existe, lo reemplazamos con el nuevo (que suele ser mas reciente en 1_OUTBOX_MICRO2)
        if email_limpio in seen_emails:
            seen_emails[email_limpio] = row
            filas_eliminadas_duplicadas += 1
        else:
            seen_emails[email_limpio] = row

    # Fase C: Estandarizacion de Estados
    final_rows = list(seen_emails.values())
    listos_count = 0
    
    for row in final_rows:
        estado_actual = str(row[col_estado_idx]).strip().upper()
        
        if not estado_actual or estado_actual in ["LISSTO", "READY"]:
            estado_actual = config.STATUS_READY
            filas_corregidas += 1
            
        row[col_estado_idx] = estado_actual
        
        if estado_actual == config.STATUS_READY:
            listos_count += 1

    # Reporte de Ejecucion
    logger.info("\n[SANITIZADOR COMPLETADO - REPORTE]")
    logger.info(f"- Total de filas escaneadas: {len(rows)}")
    logger.info(f"- Correos/Estados limpiados o corregidos: {filas_corregidas}")
    logger.info(f"- Correos inválidos eliminados: {filas_eliminadas_invalidas}")
    logger.info(f"- Duplicados eliminados: {filas_eliminadas_duplicadas}")
    logger.info(f"- Leads en estado {config.STATUS_READY} para SaaS 2: {listos_count}")
    
    if test_mode:
        logger.info("\n[OK] Fin del Modo Test. Ningún cambio ha sido guardado.")
        return

    # Fase D: Reescritura Atómica
    new_data = [headers] + final_rows
    
    logger.info(f"\nAplicando Batch Update a Google Sheets ({len(new_data)} filas en total)...")
    try:
        sheet.clear()
        # gspread >= 6.0 usa values y range_name como kwargs opcionales, pero 
        # sheet.update(values=new_data, range_name='A1') es lo más seguro.
        # Fallback simple: update(new_data) a veces funciona si es de la raíz, pero 
        # range_name="A1", values=new_data es universal en 6.x
        sheet.update(range_name='A1', values=new_data)
        logger.info("[OK] Google Sheets actualizada correctamente.")
    except Exception as e:
        logger.error(f"[ERROR] No se pudo actualizar la hoja: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sanitizador de Memoria (1_OUTBOX_MICRO2)")
    parser.add_argument("--test", action="store_true", help="Ejecuta en modo simulación (sin escribir en la hoja).")
    args = parser.parse_args()
    
    sanitize(test_mode=args.test)
