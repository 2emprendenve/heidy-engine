# drafts_api.py — Draft Review System endpoints
# Se importa en api_v2.py via: from drafts_api import register_drafts_routes
import time
import logging
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

_draft_store = []   # list of {empresa, email, subject, html, lead, ai, approved}


def register_drafts_routes(app, get_sheet_fn, read_pending_fn, generate_batch_fn, send_email_fn):

    @app.post("/api/drafts/generate")
    async def generate_drafts(data: dict = {}):
        """Genera N borradores con HTML completo para revision en el panel."""
        global _draft_store
        n = int(data.get("n", 10))
        try:
            # Limpiar caches para forzar generacion fresca desde la API
            import engine_v2 as _eng
            _eng._prompt_cache["apertura"] = None
            _eng._prompt_cache["cierre"] = None
            _eng._save_cache({})  # vaciar draft_cache.json
            logging.info("Cache limpiado. Generando borradores frescos...")

            sheet = get_sheet_fn()
            leads = read_pending_fn(sheet, n=n)
            if not leads:
                return {"status": "error", "message": "No hay leads disponibles."}

            results = generate_batch_fn(leads, force_refresh=True)
            _draft_store = []

            for r in results:
                if r.get("ai_error"):
                    continue
                html_body = r.get("Propuesta_HTML", "")
                if not html_body:
                    html_body = (
                        '<div style="font-family:Arial,sans-serif;color:#333;font-size:14px;max-width:600px;line-height:1.5;">'
                        + "<p><b>" + str(r.get("Intro_Equipo", "")) + "</b></p>"
                        + "<p>" + str(r.get("Parrafo_Mercado", "")) + "</p>"
                        + "<p>" + str(r.get("Parrafo_Emocional", "")) + "</p>"
                        + "<p>" + str(r.get("Pregunta_Cierre", "")) + "</p>"
                        + '<p style="font-size:12px;color:#777;">' + str(r.get("PD_Urgencia", "")) + "</p>"
                        + "</div>"
                    )
                _draft_store.append({
                    "empresa":  r.get("EMPRESA", "Sin nombre"),
                    "email":    r.get("EMAIL", ""),
                    "subject":  r.get("Asunto_Email", ""),
                    "html":     html_body,
                    "lead":     {k: v for k, v in r.items() if not k.startswith("_") or k == "_fila"},
                    "ai":       r,
                    "approved": False,
                })

            summary = [
                {"idx": i, "empresa": d["empresa"], "email": d["email"],
                 "subject": d["subject"], "approved": d["approved"]}
                for i, d in enumerate(_draft_store)
            ]
            return {"status": "success", "total": len(_draft_store), "drafts": summary}

        except Exception as e:
            logging.error(f"Error generando borradores: {e}")
            return {"status": "error", "message": str(e)}


    @app.get("/api/drafts/preview/{idx}")
    async def preview_draft(idx: int):
        """Devuelve el HTML completo de un borrador para mostrar en iframe."""
        if idx < 0 or idx >= len(_draft_store):
            raise HTTPException(status_code=404, detail="Borrador no encontrado")
        d = _draft_store[idx]
        html_page = (
            "<!DOCTYPE html><html><head>"
            "<meta charset='UTF-8'>"
            "<style>body{margin:20px;background:#fff;}</style>"
            "</head><body>"
            "<p style='font-size:11px;color:#888;font-family:Arial;"
            "border-bottom:1px solid #eee;padding-bottom:8px;'>"
            "<b>PARA:</b> " + d["email"] + " &nbsp;|&nbsp; "
            "<b>ASUNTO:</b> " + d["subject"] + "</p>"
            + d["html"]
            + "</body></html>"
        )
        return HTMLResponse(content=html_page)


    @app.post("/api/drafts/approve")
    async def approve_drafts(data: dict):
        """Marca uno o varios borradores como aprobados por indice."""
        indices = data.get("indices", [])
        count = 0
        for idx in indices:
            if 0 <= idx < len(_draft_store):
                _draft_store[idx]["approved"] = True
                count += 1
        return {"status": "success", "approved": count}


    @app.post("/api/drafts/send")
    async def send_approved_drafts():
        """Envia todos los borradores marcados como aprobados."""
        if not _draft_store:
            return {"status": "error", "message": "No hay borradores generados."}
        approved = [d for d in _draft_store if d["approved"]]
        if not approved:
            return {"status": "error", "message": "Ninguno aprobado. Marca al menos 1."}

        enviados, errores = 0, 0
        try:
            sheet = get_sheet_fn()
        except Exception as e:
            return {"status": "error", "message": f"Error Sheets: {e}"}

        for d in approved:
            try:
                ok = send_email_fn(d["lead"], d["ai"])
                if ok:
                    enviados += 1
                    logging.info(f"Enviado: {d['empresa']} -> {d['email']}")
                    # Marcar en Google Sheets
                    fila = d["lead"].get("_fila") or d["ai"].get("_fila")
                    if fila:
                        import engine_v2
                        from datetime import datetime
                        import gspread
                        import config
                        # Escribir ESTADO_CONTACTO, FECHA_ENVIO, ASUNTO_ENVIADO
                        try:
                            headers = sheet.row_values(1)
                            updates = []
                            if config.COL_ESTADO in headers:
                                updates.append(gspread.Cell(fila, headers.index(config.COL_ESTADO)+1, "ENVIADO"))
                            if "FECHA_ENVIO" in headers:
                                updates.append(gspread.Cell(fila, headers.index("FECHA_ENVIO")+1, datetime.now().strftime("%Y-%m-%d %H:%M")))
                            if "ASUNTO_ENVIADO" in headers:
                                updates.append(gspread.Cell(fila, headers.index("ASUNTO_ENVIADO")+1, d["subject"]))
                            if updates:
                                sheet.update_cells(updates)
                        except Exception as ex:
                            logging.warning(f"No se pudo marcar fila {fila}: {ex}")
                else:
                    errores += 1
            except Exception as e:
                errores += 1
                logging.error(f"Error enviando {d.get('email')}: {e}")
            time.sleep(2)

        return {
            "status": "success",
            "message": f"{enviados} correos enviados, {errores} errores.",
            "enviados": enviados,
            "errores": errores,
        }
