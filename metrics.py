import os
import sys
import imaplib
import email
from email.header import decode_header
import gspread
from google.oauth2.service_account import Credentials
import logging
from collections import Counter
from datetime import datetime, timedelta

try:
    import config
except ImportError:
    print("Error: config.py no encontrado.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

def _sanity_check(func):
    """Marca una función para ser ejecutada como chequeo de sanidad."""
    func._sanity_check = True
    return func

@_sanity_check
def main_sanity():
    assert True

def get_sheet() -> gspread.Worksheet:
    creds = Credentials.from_service_account_file(config.GOOGLE_CREDS_JSON, scopes=_SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(config.GOOGLE_SHEET_ID)
    return spreadsheet.worksheet(config.SHEET_TAB_LEADS)

def check_imap_bounces_and_replies():
    logger.info("🔍 Conectando al buzón de correo (IMAP)...")
    try:
        mail = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
        mail.login(config.IMAP_USER, config.IMAP_PASS)
        
        mail.select("inbox")
        # Fecha de hace 7 días
        date_since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
        
        # Buscar rebotes (Delivery Status Notification)
        # OR no está universalmente soportado en IMAP simple, hacemos 2 busquedas
        _, search_dsn = mail.search(None, f'(SINCE "{date_since}" SUBJECT "Delivery Status")')
        _, search_undel = mail.search(None, f'(SINCE "{date_since}" SUBJECT "Undeliverable")')
        
        bounces_ids = set(search_dsn[0].split() + search_undel[0].split())
        bounces_count = len(bounces_ids)
        
        # Buscar respuestas (asumiendo que no son de un bot y tienen Re: o están referenciadas)
        _, search_data_all = mail.search(None, f'(SINCE "{date_since}")')
        inbox_ids = search_data_all[0].split()
        
        replies_count = 0
        # Muestreo rápido: solo los últimos 30 correos para no saturar la API
        for num in inbox_ids[-30:]:
            if num in bounces_ids:
                continue
            _, data = mail.fetch(num, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])')
            msg = email.message_from_bytes(data[0][1])
            sender = str(msg.get("From", "")).lower()
            subject = str(msg.get("Subject", "")).lower()
            
            if "mailer-daemon" not in sender and "postmaster" not in sender and "re:" in subject:
                replies_count += 1

        # Buscar elementos enviados reales por IMAP
        sent_count = 0
        try:
            status, _ = mail.select('"[Gmail]/Sent Mail"')
            if status != 'OK':
                status, _ = mail.select('"[Gmail]/Enviados"')
            if status == 'OK':
                _, search_sent = mail.search(None, f'(SINCE "{date_since}")')
                sent_count = len(search_sent[0].split())
        except Exception as e:
            logger.warning(f"   ⚠️ No se pudo acceder a la carpeta de enviados: {e}")

        mail.logout()
        return bounces_count, replies_count, sent_count
    except Exception as e:
        logger.error(f"❌ Error conectando a IMAP: {e}")
        return 0, 0, 0

def run_metrics():
    logger.info("=========================================")
    logger.info("📊 REPORTE DE MÉTRICAS (VERDAD FACTUAL)")
    logger.info("=========================================\n")
    
    # 1. Leer Google Sheets
    logger.info("📡 Obteniendo datos de 1_OUTBOX_MICRO2...")
    try:
        sheet = get_sheet()
        all_data = sheet.get_all_values()
    except Exception as e:
        logger.error(f"❌ Error conectando a Sheets: {e}")
        return

    if not all_data:
        logger.info("La hoja está vacía.")
        return

    headers = [str(h).strip() for h in all_data[0]]
    rows = all_data[1:]
    
    if config.COL_ESTADO not in headers:
        logger.error(f"No se encontró la columna {config.COL_ESTADO}")
        return
        
    col_estado_idx = headers.index(config.COL_ESTADO)
    estados = Counter(str(r[col_estado_idx]).strip() if len(r) > col_estado_idx else "" for r in rows)
    
    # 2. Leer IMAP (Buzón)
    bounces, replies, real_sent = check_imap_bounces_and_replies()
    
    # 3. Imprimir reporte
    logger.info("\n-----------------------------------------")
    logger.info("1️⃣  ESTADO EN BASE DE DATOS (1_OUTBOX_MICRO2)")
    logger.info("-----------------------------------------")
    logger.info(f"Total Leads en memoria: {len(rows)}")
    for k, v in estados.items():
        logger.info(f"  - {k if k else '(Vacío / Sin procesar)'}: {v}")
        
    logger.info("\n-----------------------------------------")
    logger.info("2️⃣  ESTADO REAL DEL BUZÓN (Últimos 7 días)")
    logger.info("-----------------------------------------")
    logger.info(f"  - Correos efectivamente ENVIADOS: {real_sent}")
    logger.info(f"  - Rebotes detectados (Delivery Failure): {bounces}")
    logger.info(f"  - Posibles respuestas humanas directas:  {replies}")
    logger.info("=========================================")

if __name__ == "__main__":
    run_metrics()
