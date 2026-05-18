# Flujo de Trabajo

0. **[VERIFICADOR]** **Verificación externa (si aplica):** Si la tarea requiere consumir una API, endpoint o modelo externo, invocar al subagente verificador (`.ai/agents/verifier.md`) y obtener `[VERIFIED]` antes de continuar. No se planifica ni escribe código dependiente de un recurso externo sin confirmación previa.

0.5 **[PLANIFICADOR]** **Dreaming check:** Antes de planificar, leer `project_context.md` y `tech_stack.md`. Comparar dependencias y restricciones con el código real (escaneo rápido de imports en `src/`). Si alguna dependencia, API o restricción parece obsoleta o ha cambiado, advertir al usuario y ofrecer actualizar los archivos de reglas. Preguntar explícitamente: "¿Ha cambiado algo en el stack, APIs externas o restricciones desde la última sesión?".

1. **[PLANIFICADOR]** **Desglose Explícito**: antes de escribir código, enumerar los pasos (1., 2., 3.) en lenguaje natural.
2. **[PLANIFICADOR]** **Estimado de Impacto**: indicar archivos que se tocarán y líneas aproximadas.
3. **[PLANIFICADOR]** **Validación Previa**: preguntar "¿Confirmas este plan?" y esperar.
4. **[ESCRITOR]** **Ejecución**: implementar paso a paso, realizando checkpoint antes de cada modificación (ver healing.md). Cada bloque de escritura debe anunciar el archivo y el cambio concreto.
5. **[AUDITOR]** **Reporte Final**: resumir cambios y ejecutar `quick_heal.py`. Reportar resultados con formato `[OK]`, `[FAIL]` o `[TIMEOUT]`. Si hay fallos, sugerir rollback desde snapshot.
- **Restricción [HARD]**: No ejecutar más de 3 tareas en paralelo sin validación intermedia.
