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

## SECCIÓN 1: Ficha de caracterización del modelo (AA1)

| Dato | Valor |
|---|---|
| Perfil de hardware | A (24 GB RAM) |
| RAM total del equipo | 23.92 GB |
| Modelo y etiqueta | qwen2.5-coder:1.5b |
| Tamaño en disco | 986 MB |
| Latencia modelo frío (primera carga) | 6898.88 ms |
| Latencia promedio (5 llamadas, modelo caliente) | 240.5 ms |
| Latencia individual (5 mediciones) | 243.32, 238.36, 232.72, 249.44, 238.68 ms |
| RAM usada durante inferencia | ~1060.8 MB (1.04 GB) en el proceso `llama-server` (subproceso que Ollama lanza para alojar el modelo cargado); el proceso `ollama.exe` en sí se mantiene liviano (~70 MB), ya que delega la inferencia a `llama-server` |
| Calidad percibida | 5/5 — las 5 clasificaciones de prueba fueron semánticamente correctas (fix/feat/docs/refactor/test), sin ningún resultado "desconocido" |

## SECCIÓN 2: Análisis del cuello de botella (AA4, comparando P-05 vs la caracterización de ollama)

Comparando el motor `eco` bajo carga (10 usuarios concurrentes, k6: p95=16.9ms, 0% fallos, 655 requests en 2 minutos) contra el motor `ollama` en modo secuencial (sin concurrencia: promedio 240.5ms por inferencia), el motor `ollama` es aproximadamente **29x más lento** que el motor `eco` incluso en su mejor caso (modelo ya cargado en memoria). El cuello de botella real está en la inferencia del LLM: aunque el modelo esté "caliente", cada llamada sigue compitiendo por CPU y RAM para generar tokens, mientras que el motor `eco` (regex) es prácticamente gratis en comparación — no hay cómputo de modelo involucrado, solo evaluación de patrones sobre texto. La API (FastAPI) y PostgreSQL no son el cuello de botella en ningún caso; su aporte a la latencia total es marginal frente al tiempo de inferencia del modelo. El hallazgo más relevante es la brecha entre carga fría (6.9s) y caliente (240ms): el costo de arranque del modelo es, por mucho, el peor caso a evitar en producción — una primera petición después de inactividad pagaría un costo ~29x mayor que las siguientes.

## SECCIÓN 3: Propuestas de mejora

1. **Mantener el modelo cargado con `OLLAMA_KEEP_ALIVE`.** Por defecto Ollama descarga el modelo de memoria tras 5 minutos de inactividad, lo que reintroduce el costo de carga fría (~6.9s) en la siguiente petición. Con RAM suficiente (Perfil A, 24 GB, y el modelo usando solo ~1 GB), conviene fijar `OLLAMA_KEEP_ALIVE=-1` (o un valor alto) para que el modelo permanezca residente y todas las peticiones paguen la latencia "caliente" (~240ms), no la fría.
2. **Cache de resultados para mensajes de commit repetidos o muy similares.** Muchos mensajes de commit en un equipo real se repiten o son casi idénticos (ej. "corrige typo", "actualiza dependencias"). Un cache simple por hash del texto normalizado evitaría invocar al modelo para entradas ya vistas, reduciendo tanto la latencia percibida como la carga de CPU.
3. **Limitar la concurrencia hacia Ollama con una cola o semáforo.** Como la inferencia compite por el mismo proceso `llama-server` cargado en memoria, peticiones simultáneas hacia el motor `ollama` se serializarían de todas formas a nivel de hardware; sin un límite explícito en la API, ráfagas de tráfico podrían saturar CPU/RAM o degradar la latencia de forma impredecible. Una cola con concurrencia limitada (ej. un semáforo de 1-2 peticiones simultáneas hacia Ollama) evita ese efecto y da tiempos de respuesta más predecibles bajo carga real.
