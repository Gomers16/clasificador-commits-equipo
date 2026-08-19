# Manual Técnico

## Arquitectura

```
Cliente (curl, Postman, etc.)
   |
   |  HTTP :8000 (JSON)
   v
API FastAPI -- contenedor "api"
   GET  /health
   POST /clasificar
   GET  /inferencias
   |
   |-- motor="eco"    --> Motor eco: clasificacion por reglas regex,
   |                      en el mismo proceso, sin red, sin modelo
   |
   |-- motor="ollama" --> Motor ollama: HTTP POST a
   |                      host.docker.internal:11434/api/generate
   |                      (Ollama corre nativo en el host Windows,
   |                      fuera de Docker)
   |
   v  (ambos motores guardan el resultado aqui)
PostgreSQL -- contenedor "db", puerto 5432
   tabla inferencias
```

**Componentes:**

- **Cliente:** cualquier consumidor HTTP (curl, Postman, un frontend futuro). Habla JSON sobre HTTP con la API.
- **API FastAPI (`api`):** expone `GET /health`, `POST /clasificar` y `GET /inferencias` en el puerto 8000. Decide qué motor usar según el campo `motor` del request, ejecuta la clasificación, guarda el resultado en Postgres y responde.
- **Motor eco:** clasificación por reglas regex (`REGLAS_CLASIFICACION` en `app/main.py`), corre dentro del mismo proceso de la API, sin llamadas de red ni dependencia de un modelo. Es el motor por defecto.
- **Motor ollama:** delega la clasificación a un LLM real (`qwen2.5-coder:1.5b`) vía HTTP a `http://host.docker.internal:11434/api/generate`. Ollama corre nativo en el host Windows, no está contenerizado — el contenedor `api` le llega a través de `host.docker.internal`, el hostname especial que Docker Desktop resuelve al host.
- **PostgreSQL (`db`):** contenedor con la tabla `inferencias`, donde se registra cada clasificación (motor, modelo, entrada, salida, latencia, fecha). Inicializa su esquema automáticamente vía `db/init.sql` la primera vez que se crea el volumen.

## Seguridad

**Puertos expuestos:**

| Puerto | Servicio | Por qué está expuesto |
|---|---|---|
| 8000 | API (`api`) | Necesario para que el cliente/consumidor externo llegue a la API. |
| 5432 | PostgreSQL (`db`) | Expuesto **solo para desarrollo local**, para poder correr `pytest` desde el host (fuera de los contenedores) contra la base de datos real. **En un despliegue de producción real, este puerto no debería publicarse al host** — la API ya le llega a `db` por la red interna de Docker (`red_ia`), y exponer Postgres directamente amplía la superficie de ataque sin necesidad. |

**Roles en la base de datos** (definidos en `db/init.sql`):

- **`postgres`** (superusuario): usado únicamente para inicializar el esquema (`CREATE ROLE`, `CREATE TABLE`, `GRANT`) y para operaciones administrativas (respaldos, restauraciones). No lo usa la API en su día a día.
- **`app_ia`** (rol de aplicación, el que usa la API vía `DB_USER`/`DB_PASSWORD`): privilegios mínimos — `GRANT SELECT, INSERT ON TABLE inferencias` y `GRANT USAGE, SELECT ON SEQUENCE inferencias_id_seq`. **Sin `DELETE`, `UPDATE` ni `DROP`.** Esto se verificó en la prueba de acceso P-04: intentar `DELETE FROM inferencias` y `DROP TABLE inferencias` con este rol produce `permission denied` y `must be owner of table`, respectivamente.

**Manejo de secretos:**

- `.env` (con las credenciales reales) está en `.gitignore` — nunca se sube a git.
- `.env.example` es la plantilla versionada, con placeholders (`changeme_admin`, `changeme_app_ia`) en vez de contraseñas reales.

**Qué hacer si se filtra una contraseña:**

1. Rotarla inmediatamente en Postgres: `ALTER ROLE app_ia WITH PASSWORD 'nueva_contrasena';` (con el superusuario `postgres`).
2. Actualizar `DB_PASSWORD` en `.env` con el mismo valor nuevo.
3. Reiniciar el contenedor `api` para que tome la variable de entorno actualizada: `docker compose up -d --build api` (o `docker compose restart api` si no cambió el código).
4. Revisar logs de acceso sospechoso (`docker compose logs db`, y logs de conexión de Postgres si están habilitados) para detectar uso indebido de la contraseña filtrada.
5. **Si el `.env` llegó a subirse a git por error:** no basta con un commit nuevo que lo elimine — la contraseña vieja queda visible en el historial de git para siempre. Hay que **invalidar esa contraseña** (rotarla, paso 1) **y además purgar el historial** (ej. con `git filter-repo` o BFG Repo-Cleaner) para eliminar el archivo de todos los commits pasados, luego forzar el push del historial reescrito y notificar al equipo para que resincronice sus clones.

## Endpoints

| Método | Ruta | Entrada | Respuesta de ejemplo | Errores posibles |
|---|---|---|---|---|
| `GET` | `/health` | Ninguna | `{"status": "ok"}` | — |
| `POST` | `/clasificar` | Body JSON: `{"texto": "<string>", "motor": "eco" \| "ollama"}` (`motor` es opcional, default `"eco"`) | `{"motor": "eco", "modelo": "eco-reglas-v1", "entrada": "corrige el error de login", "tipo": "fix", "latencia_ms": 14.2}` | `422` si falta `texto` o `motor` tiene un valor fuera de `"eco"`/`"ollama"` (validación Pydantic); `502` si `motor="ollama"` y falla la conexión a Ollama (`Error consultando Ollama: ...`); `500` si falla la conexión a PostgreSQL |
| `GET` | `/inferencias` | Query param opcional `limite` (int, default `20`) | `[{"id": 671, "motor": "eco", "modelo": "eco-reglas-v1", "entrada": "...", "salida": "fix", "latencia_ms": 14.2, "fecha": "2026-08-19T03:26:12.82"}, ...]` (array ordenado por `id` descendente) | `500` si falla la conexión a PostgreSQL |

## Modelo de datos

Tabla `inferencias` (definida en `db/init.sql`):

| Columna | Tipo | Constraint | Significado |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Identificador autoincremental del registro. |
| `motor` | `VARCHAR(20)` | `NOT NULL`, `CHECK (motor IN ('eco', 'ollama'))` | Qué motor de clasificación se usó para esta inferencia. |
| `modelo` | `VARCHAR(100)` | `NOT NULL` | Identificador del modelo/versión usado (ej. `eco-reglas-v1` para el motor por reglas, o `qwen2.5-coder:1.5b` para Ollama). |
| `entrada` | `TEXT` | `NOT NULL` | Texto original enviado a clasificar (`texto` del request). |
| `salida` | `TEXT` | (nullable) | Resultado de la clasificación — el `tipo` devuelto (`fix`, `feat`, `docs`, `test`, `chore`, `refactor`, o `desconocido` si el motor `ollama` respondió algo fuera de esas categorías). |
| `latencia_ms` | `DOUBLE PRECISION` | `NOT NULL` | Tiempo que tardó en procesar la clasificación, en milisegundos. |
| `fecha` | `TIMESTAMP` | `NOT NULL`, `DEFAULT NOW()` | Fecha y hora del registro. |

El rol `app_ia` tiene `SELECT, INSERT` sobre esta tabla y `USAGE, SELECT` sobre su secuencia `inferencias_id_seq` — puede insertar nuevas inferencias y leerlas, pero no modificarlas ni borrarlas (ver sección Seguridad).

## Decisiones de diseño y limitaciones

**Decisiones:**

- **Dockerfile multi-etapa:** la etapa `builder` instala las dependencias de Python con las herramientas de compilación necesarias; la etapa final solo copia los paquetes ya instalados (`COPY --from=builder /install /usr/local`) y el código de `app/`. Esto deja una imagen final más liviana, sin compiladores ni artefactos de build que no se necesitan en tiempo de ejecución.
- **Usuario sin privilegios en el contenedor (`appuser`, UID 1001):** el `Dockerfile` crea este usuario y ejecuta la aplicación con `USER appuser` en vez de como root. Si un atacante lograra ejecutar código dentro del contenedor, quedaría limitado a los permisos de un usuario sin privilegios, reduciendo el impacto de una posible fuga del contenedor.
- **Motor `eco` como default/liviano:** al ser clasificación por reglas regex sin dependencias externas, permite que el proyecto funcione en cualquier equipo del curso sin necesidad de tener Ollama instalado ni un modelo descargado — útil para desarrollo, pruebas rápidas y como fallback si Ollama no está disponible.
- **Privilegios mínimos en la base de datos:** el rol `app_ia` solo puede `SELECT`/`INSERT`, siguiendo el principio de mínimo privilegio. Si la API llegara a comprometerse (ej. por una vulnerabilidad de inyección o una dependencia maliciosa), el atacante no podría borrar ni alterar los datos históricos ya guardados, limitando el daño posible.

**Limitaciones conocidas:**

- El motor `eco` es una heurística simple basada en regex — puede clasificar mal textos ambiguos, textos en otros idiomas, o mensajes que no mapean claramente a ninguna palabra clave (cae a `chore` por defecto).
- El motor `ollama` depende de que Ollama esté corriendo en el host — no está contenerizado, así que si Ollama no está activo (o el host no es accesible vía `host.docker.internal`), las peticiones con `motor="ollama"` fallan con `502`.
- No hay autenticación ni autorización en los endpoints de la API — cualquiera que tenga acceso de red al puerto 8000 puede usarla libremente, sin restricción de usuario ni rol.
- No hay rate limiting — no hay ningún límite sobre cuántas peticiones por segundo/minuto puede mandar un cliente, lo que deja el servicio expuesto a abuso o saturación accidental (especialmente relevante para el motor `ollama`, mucho más costoso en CPU que `eco`).

## Respaldo y restauración

### Comando de respaldo recomendado

El esquema de la base de datos (tablas, roles, permisos) vive en `db/init.sql` y es reproducible por sí mismo — no hace falta duplicarlo en cada respaldo. Por eso el respaldo debe hacerse con `--data-only`, que solo exporta los datos, no la estructura:

```powershell
docker compose exec -T db pg_dump -U postgres --data-only clasificador_commits > backups/respaldo_YYYY-MM-DD.sql
```

Reemplaza `YYYY-MM-DD` por la fecha real (ej. con `Get-Date -Format 'yyyy-MM-dd'` en PowerShell). Los archivos generados quedan en `backups/`, carpeta ignorada por git (`.gitignore`) — nunca se debe subir un `.sql` con datos reales al repositorio.

### Procedimiento de restauración

1. Asegurar que el esquema existe en la base de destino (la tabla `inferencias` y el rol `app_ia`, definidos en `db/init.sql`). Esto ocurre automáticamente la primera vez que se levanta el contenedor `db` con un volumen vacío, vía `docker-entrypoint-initdb.d`. Si es una base nueva sin inicializar, basta con:
   ```powershell
   docker compose up -d db
   ```
   y esperar a que termine de correr `init.sql` (se puede verificar con `docker compose ps`, esperando el estado `healthy`).
2. Restaurar solo los datos:
   ```powershell
   Get-Content backups/respaldo_YYYY-MM-DD.sql | docker compose exec -T db psql -U postgres -d clasificador_commits
   ```
   Al ser un respaldo `--data-only`, este paso solo ejecuta `COPY` sobre las tablas existentes — no debería mostrar warnings de `relation already exists` (esos warnings solo aparecen al restaurar un dump completo, con `CREATE TABLE` incluido, sobre un esquema que ya existe).
3. Verificar el conteo de filas para confirmar que la restauración fue completa:
   ```powershell
   docker compose exec -T db psql -U postgres -d clasificador_commits -c "SELECT COUNT(*) FROM inferencias;"
   ```

**Por qué `--data-only` evita conflictos:** un respaldo completo (`pg_dump` sin `--data-only`) incluye las sentencias `CREATE TABLE`, `CREATE SEQUENCE` y las constraints del esquema. Si se restaura ese dump completo sobre una base donde el esquema ya existe (como pasó en la prueba de este documento, donde se usó un dump completo sobre una tabla truncada pero no eliminada), esas sentencias fallan con errores como `relation "inferencias" already exists` o `multiple primary keys for table "inferencias" are not allowed` — no rompen la restauración de los datos, pero ensucian la salida. Con `--data-only`, el dump solo contiene `COPY` de los datos, así que se restaura sobre un esquema ya inicializado sin ningún conflicto ni warning.

### Periodicidad y responsable

- **Periodicidad propuesta:** un respaldo antes de cada actualización mayor (cambios de esquema, migraciones, releases), y de forma diaria si el sistema está recibiendo tráfico real en producción.
- **Responsable:** rotativo entre el equipo — la persona que tenga el turno de despliegue esa semana es quien ejecuta y verifica el respaldo antes de aplicar cambios.

### Evidencia de la prueba de restauración real

Se ejecutó una prueba completa de desastre simulado para validar que el procedimiento de respaldo funciona de extremo a extremo. Esta prueba se hizo con un dump completo (sin `--data-only`, antes de adoptar esta recomendación) sobre una tabla truncada pero no eliminada — por eso se observaron los warnings de `relation already exists` descritos arriba. Los resultados de datos son válidos igual, ya que esos warnings no afectan la restauración de las filas:

| Momento | Conteo de filas en `inferencias` |
|---|---|
| Antes del desastre simulado | 671 |
| Después de `TRUNCATE inferencias` (desastre simulado) | 0 |
| Después de restaurar desde el respaldo | 671 |

El conteo de filas coincidió exactamente antes y después de la restauración, confirmando que el respaldo es válido y el procedimiento de recuperación funciona.
