import os
import gspread
from google.oauth2.service_account import Credentials
import config
from pprint import pprint

creds = Credentials.from_service_account_file(config.GOOGLE_CREDS_JSON, scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds)
sheet = gc.open_by_key(config.GOOGLE_SHEET_ID).worksheet(config.SHEET_TAB_LEADS)

data = sheet.get_all_values()
headers = data[0]

print("--- ALINEACIÓN DE COLUMNAS (Fila 2) ---")
if len(data) > 1:
    row2 = data[1]
    for i, h in enumerate(headers):
        val = row2[i] if i < len(row2) else "(vacío)"
        print(f"Col {i+1} [{h}]: {val}")
