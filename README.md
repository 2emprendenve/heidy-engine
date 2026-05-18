# Micro SaaS 2 — Motor de Ventas Humanista
### Para José Rafael Bravo León

Este sistema automatiza el contacto inicial con leads, la clasificación de respuestas y el seguimiento hacia un embudo de Kajabi, todo con un enfoque humanista y minimalista.

## 🚀 Inicio Rápido8

1.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configurar credenciales:**
    *   Copia `.env.example` a `.env` y rellena tus datos.
    *   Coloca tu `credentials.json` (Service Account de Google) en la carpeta raíz.
    *   Asegúrate de que el email de la Service Account sea **Editor** en tu Google Sheet.
3.  **Preparar Ollama (Gratis):**
    *   Descarga [Ollama](https://ollama.com).
    *   Ejecuta: `ollama pull llama3.2`
4.  **Ejecutar Prueba:**
    ```bash
    python main.py
    ```

## 🌉 Arquitectura Puente (Sincronización)

Para evitar colisiones de datos entre el **Micro SaaS 1 (Extractor)** y el **Micro SaaS 2 (El Tigre)**, la Google Sheet actúa como una base de datos con estados definidos:

1.  **Micro SaaS 1 (Escritura)**: Extrae leads y escribe en la fila. Al terminar, debe marcar `ESTADO = LISTO`.
2.  **Micro SaaS 2 (El Tigre)**:
    - **Filtro**: Solo lee filas donde `ESTADO == LISTO`.
    - **Semáforo**: Inmediatamente marca el lote como `PROCESANDO`.
    - **Cierre**: Tras el envío exitoso, marca `ENVIADO` y guarda la `PROPUESTA_REDACTADA`.
    - **Errores**: Si falta el email o el dolor es insuficiente, marca `ERROR_DATA`.
3.  **Modo Producción (`DRY_RUN=false`):** Procesa leads de 10 en 10, con pausas de 1 minuto entre correos y 15 segundos entre lotes. Límite: 50 correos/día.

## 🛠️ Modos de Operación

1.  **Modo TEST (`TEST_EMAIL` en .env):** Toma 1 lead al azar y te envía una "Identificación Completa" a tu correo para que valides el copy de la IA antes de lanzar todo.
2.  **Modo Simulación (`DRY_RUN=true`):** No envía correos ni quema tokens reales. Imprime todo en la terminal.

## 🧠 Estructura del Copy

El sistema lee `prompt_estrategico.txt`. Puedes editar ese archivo para cambiar la voz de José Rafael o las reglas de escritura sin tocar el código Python.

## 📬 Seguimiento IMAP

El script escucha tu Gmail cada 30 minutos. Si alguien responde positivamente (clasificado por Ollama local), el sistema le envía un segundo correo con el enlace a tu página de Kajabi.
*   **Seguridad:** Utiliza el header `In-Reply-To` para asegurar que solo responde a hilos que iniciamos nosotros.
*   **Privacidad:** Nunca menciona precios en los correos.

## 📊 Métricas

El sistema crea automáticamente una pestaña llamada **Métricas** en tu Google Sheet donde verás:
*   Emails enviados hoy.
*   Tasa de rebotes.
*   Respuestas positivas detectadas.
*   Log detallado de cada acción.
