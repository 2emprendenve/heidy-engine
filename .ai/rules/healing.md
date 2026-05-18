# Protocolo de Auto-Sanación

- **Principio:** Si se detecta un error (alucinación, código roto, violación de estándares), aplicar:
  1. **STOP**: Detener la generación actual.
  2. **SNAPSHOT**: Leer `.ai/state_snapshot.json` para identificar el último checkpoint.
  3. **ROLLBACK**: Restaurar los archivos modificados a sus hashes del snapshot. Si no existe snapshot, informar al usuario.
  4. **EXPLAIN**: Explicar en 1-2 líneas qué falló (sin excusas).
  5. **FIX**: Proponer una corrección mínima y verificable.

- **Checkpointing obligatorio [HARD]:** Antes de modificar cualquier archivo, el agente debe generar (o actualizar) `.ai/state_snapshot.json`. Este archivo contiene un diccionario con `{"nombre_archivo": "hash_md5"}` de los archivos que van a ser modificados. Si el snapshot no existe aún, se debe crear tomando todos los `.py` y `.html` del proyecto.
  - Ejemplo de generación: `hashlib.md5(open(f,'rb').read()).hexdigest()`.

- **Shotgun Verify para APIs externas [HARD]:** Cuando una implementación dependa de un servicio, API o versión de modelo externo, nunca asumir disponibilidad. Ejecutar un script de prueba que verifique la conectividad probando las opciones más probables. Fijar la primera opción exitosa con `# VERIFIED: <recurso>`.

- **Script `quick_heal.py`:** Recorre `src/`, compila cada `.py` con `python -m py_compile`, ejecuta con timeout de 5s. Si una función está decorada con `@sanity`, la ejecuta aisladamente. Reporta `[OK]`, `[FAIL]` o `[TIMEOUT]`. Si hay `[FAIL]`, consulta `state_snapshot.json` y sugiere rollback.
