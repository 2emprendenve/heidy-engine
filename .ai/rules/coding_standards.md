# Estándares de Código

- **Estilo [HARD]:** Minimalista, código limpio, modular y auto-documentado (nombres descriptivos).
- **Self-Check obligatorio [HARD]:** Todo nuevo módulo o función debe incluir al final del archivo un bloque `if __name__ == "__main__":` (o equivalente) que ejecute al menos 2 asserts o tests simples que demuestren que la funcionalidad principal opera. Esto es un **"sanity check" automático**, no un test suite completo.
- **Principio del Cambio Mínimo [HARD]:** Solo modificar el código mínimo necesario para la tarea actual. Prohibido hacer refactorizaciones sistémicas no solicitadas.
- **Crítica constructiva [SOFT]:** Cuestionar brevemente si una instrucción compromete la simplicidad. Si el usuario insiste, obedecer sin volver a cuestionar. Usar el formato: `⚠️ Advertencia: [riesgo]. ¿Procedo de todas formas?`
- **Opcional:** Se puede marcar una función con un decorador `@sanity` (provisto en `.ai/scripts/sanity.py`) para que `quick_heal.py` la ejecute aisladamente como chequeo adicional.
