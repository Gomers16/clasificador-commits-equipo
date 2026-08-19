# Informe Técnico — Plan de Pruebas del Despliegue (AA4)

## Resultados de pruebas

| ID   | Tipo      | Qué se verifica                                                       | Resultado esperado                                    | Obtenido                                              | Estado |
|------|-----------|------------------------------------------------------------------------|---------------------------------------------------------|--------------------------------------------------------|--------|
| P-01 | Funcional | `GET /health` responde                                                 | `200` y `{"status": "ok"}`                               | `200` y `{"status": "ok"}`                                | OK     |
| P-02 | Funcional | `POST /clasificar` motor `eco` con texto de tipo fix                   | `tipo` correcto (`"fix"`)                                | `tipo: "fix"`                                             | OK     |
| P-03 | Funcional | `POST /clasificar` con texto que no matchea ninguna regla              | `tipo` por defecto `"chore"`                             | `tipo: "chore"`                                            | OK     |
| P-04 | Acceso    | Rol `app_ia` intenta `DELETE`/`DROP` sobre la tabla `inferencias`      | Error de permisos en ambos casos                         | `ERROR: permission denied for table inferencias` / `ERROR: must be owner of table inferencias` | OK     |
| P-05 | Carga     | 10 usuarios concurrentes sobre motor `eco` (k6, 30s→5, 1min→10, 30s→0) | `p(95) < 800ms` y tasa de errores `< 5%`                 | `p(95) = 16.9ms`, `0%` fallos, `655` requests totales      | OK     |

## Análisis

El motor `eco` (clasificación por reglas regex, sin modelo de lenguaje) resultó extremadamente liviano bajo carga: latencia promedio de ~14ms y p95 de ~17ms con 10 usuarios concurrentes, muy por debajo del umbral de 800ms definido en la prueba de carga, con 0% de errores sobre 655 requests. Esto confirma que el servicio en sí (FastAPI + Postgres) no representa un cuello de botella para este motor.

El costo real de latencia del sistema se espera que venga del motor `ollama`, que delega la clasificación a un LLM real vía HTTP. Esa caracterización de rendimiento queda pendiente para una etapa posterior del curso, cuando se mida el motor `ollama` bajo las mismas condiciones de carga.
