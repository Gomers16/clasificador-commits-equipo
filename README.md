# Clasificador de Commits IA

API REST que clasifica mensajes de commit en las categorías estándar de Conventional Commits (`feat`, `fix`, `docs`, `test`, `chore`, `refactor`), usando dos motores intercambiables:

- **`eco`**: clasificación por reglas (regex), instantánea, sin dependencias externas.
- **`ollama`**: clasificación con un LLM local (Qwen 2.5 Coder 1.5B) vía [Ollama](https://ollama.com), con mayor comprensión semántica.

Cada clasificación queda registrada en PostgreSQL con su motor, modelo, entrada, resultado y latencia. Todo el stack corre contenerizado con Docker, con un pipeline de integración continua en GitHub Actions que valida estilo de código, construcción de la imagen y pruebas automatizadas en cada cambio.

## Integrante

- **Diego Mauricio Gómez Rodríguez** — Perfil A (24 GB RAM)

## Requisitos mínimos

| Requisito | Detalle |
|---|---|
| Docker Desktop | Con backend WSL2 (Windows) o Docker Engine nativo (Linux/Mac) |
| Ollama | Opcional — solo si vas a usar `motor="ollama"`. Descarga en https://ollama.com |
| Git | Cualquier versión reciente |
| RAM | 4 GB mínimo para el stack base; 8 GB+ recomendado si usas Ollama |
| Espacio en disco | ~2 GB (imágenes Docker + modelo de Ollama si se instala) |

## Instalación

Todos los comandos están en PowerShell (Windows). Si usas Linux/Mac, ajusta la sintaxis de variables de entorno según corresponda.

### 1. Clonar el repositorio

```powershell
git clone https://github.com/Gomers16/clasificador-commits-equipo.git
cd clasificador-commits-equipo
```

### 2. Configurar variables de entorno

```powershell
Copy-Item .env.example .env
```

Abre `.env` y ajusta SOLO estos dos valores según tu preferencia (son de libre elección, no afectan la coherencia del sistema):

- `POSTGRES_PASSWORD` — contraseña del superusuario de Postgres, puedes poner cualquier valor.
- `OLLAMA_MODEL` — solo si vas a usar el motor ollama, ajústalo al modelo que descargues.

**Deja el resto de las variables EXACTAMENTE como están en el archivo, sin cambiarlas:**

- `DB_PASSWORD=app_ia_password` — este valor NO es un placeholder, es la contraseña real del rol `app_ia`, ya definida de forma fija en `db/init.sql` (`CREATE ROLE app_ia WITH LOGIN PASSWORD 'app_ia_password'`). Si la cambias en `.env` sin cambiarla también en `db/init.sql`, la API no podrá autenticarse contra la base de datos.
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` — coinciden con nombres fijos definidos en `docker-compose.yml` y `db/init.sql`; no deben modificarse en un despliegue local estándar.

**Nunca subas tu `.env` real a git** (ya está en `.gitignore`).

### 3. Levantar el stack completo

```powershell
docker compose up -d --build
```

Esto construye la imagen de la API y levanta dos contenedores: `api` (FastAPI, puerto 8000) y `db` (PostgreSQL 16, puerto 5432). El esquema de base de datos (tabla `inferencias`, rol `app_ia` con privilegios mínimos) se crea automáticamente en el primer arranque, vía `db/init.sql`.

Verifica que ambos servicios estén corriendo:

```powershell
docker compose ps
```

Deberías ver `api` en estado `Up` y `db` en estado `healthy`.

### 4. (Opcional) Instalar Ollama para el motor `ollama`

Si quieres usar clasificación con LLM real, no solo por reglas:

```powershell
winget install -e --id Ollama.Ollama
```

Descarga el modelo correspondiente a tu perfil de hardware (ver tabla de perfiles más abajo):

```powershell
ollama pull qwen2.5-coder:1.5b
```

Confirma que Ollama responde:

```powershell
Invoke-RestMethod -Uri http://localhost:11434/api/generate -Method Post -ContentType "application/json" -Body '{"model":"qwen2.5-coder:1.5b","prompt":"hola","stream":false}'
```

### Perfiles de hardware y modelo recomendado

| Perfil | RAM | Modelo | Tamaño |
|---|---|---|---|
| A | 16 GB o más | `qwen2.5-coder:1.5b` | ~1 GB |
| B | 8 GB | `qwen2.5:0.5b` | ~400 MB |
| C | 4 GB (o disco mecánico) | `gemma3:270m` | ~300 MB |

Ajusta `OLLAMA_MODEL` en tu `.env` según el modelo que descargues.

## Cómo verificar que todo funciona

### Health check

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Respuesta esperada:
```json
{"status": "ok"}
```

### Clasificar un commit (motor eco)

```powershell
Invoke-RestMethod -Uri http://localhost:8000/clasificar -Method Post -ContentType "application/json" -Body '{"texto": "corrige el error de conexion a la base de datos", "motor": "eco"}'
```

Respuesta esperada:
```json
{
  "motor": "eco",
  "modelo": "eco-reglas-v1",
  "entrada": "corrige el error de conexion a la base de datos",
  "tipo": "fix",
  "latencia_ms": 14.2
}
```

### Clasificar con el modelo local (motor ollama)

```powershell
Invoke-RestMethod -Uri http://localhost:8000/clasificar -Method Post -ContentType "application/json" -Body '{"texto": "agrega el endpoint de historial", "motor": "ollama"}'
```

La primera llamada tarda varios segundos (el modelo debe cargarse en memoria); las siguientes son mucho más rápidas (~240ms en Perfil A).

### Ver el historial de clasificaciones

```powershell
Invoke-RestMethod http://localhost:8000/inferencias
```

También puedes explorar todos los endpoints de forma interactiva en **http://localhost:8000/docs** (documentación autogenerada por FastAPI).

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Verifica que la API y la base de datos estén disponibles |
| `POST` | `/clasificar` | Clasifica un mensaje de commit. Body: `{"texto": str, "motor": "eco"\|"ollama"}` |
| `GET` | `/inferencias?limite=20` | Lista las últimas clasificaciones registradas |

Ver `docs/manual-tecnico.md` para el detalle completo de arquitectura, seguridad, modelo de datos y decisiones de diseño.

## Solución de problemas

Errores reales que ocurrieron durante el desarrollo de este proyecto, con su causa y solución:

### 1. VS Code detecta Python solo como "alias de Microsoft Store"

**Síntoma:** al ejecutar `python --version` se abre la tienda de Windows en vez de mostrar la versión.
**Causa:** Windows deja un ejecutable falso de Python que solo abre la Store.
**Solución:** instalar Python real desde https://www.python.org/downloads/, marcando la casilla **"Add python.exe to PATH"** durante la instalación. Opcionalmente, desactivar el alias fantasma en *Configuración → Aplicaciones → Alias de ejecución de aplicaciones*.

### 2. Un programa recién instalado con `winget` no se reconoce en la terminal

**Síntoma:** después de `winget install ...` (por ejemplo `gh` o `ollama`), el comando da `no se reconoce como nombre de un cmdlet`.
**Causa:** PowerShell no recarga automáticamente el PATH del sistema en sesiones ya abiertas.
**Solución:** abrir una terminal PowerShell nueva. Si sigue sin reconocerlo, forzar la recarga del PATH sin reiniciar:
```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```

### 3. `pytest` funciona en local pero falla en CI con `ModuleNotFoundError: No module named 'app'`

**Síntoma:** las pruebas pasan en la máquina local pero el pipeline de GitHub Actions falla con ese error de import.
**Causa:** localmente se corría con `python -m pytest`, que agrega automáticamente el directorio actual a `sys.path`. El CI ejecuta `pytest` a secas, que sin un `tests/__init__.py` no encuentra el paquete `app` desde la raíz del repositorio.
**Solución:** agregar un archivo `tests/__init__.py` vacío. Esto hace que pytest resuelva los imports desde la raíz del repo sin importar cómo se invoque el comando.

### 4. Las pruebas fallan con `Connection refused` al conectarse a PostgreSQL desde el host

**Síntoma:** `psycopg2.OperationalError: connection to server at "localhost", port 5432 failed: Connection refused`.
**Causa:** el servicio `db` en `docker-compose.yml` no publicaba el puerto 5432 al host — solo era accesible dentro de la red interna de Docker.
**Solución:** agregar `ports: ["5432:5432"]` al servicio `db`, y exportar `DB_HOST=localhost` (en vez de `db`, que solo resuelve dentro de la red de Compose) antes de correr `pytest` desde fuera de los contenedores.

### 5. `docker build` falla con `failed to connect to the docker API... dockerDesktopLinuxEngine`

**Síntoma:** cualquier comando `docker` falla con un error de conexión al pipe `dockerDesktopLinuxEngine`.
**Causa:** Docker Desktop no está abierto, o el motor (backend WSL2) no terminó de inicializar.
**Solución:** abrir Docker Desktop manualmente desde el menú de Inicio y esperar a que el ícono de la ballena en la bandeja del sistema deje de animarse (o que la app muestre "Engine running") antes de reintentar el comando.

## Video de demostración

*— pendiente de grabar —*

## Documentación adicional

- [`docs/manual-tecnico.md`](docs/manual-tecnico.md) — arquitectura, seguridad, modelo de datos, respaldo y restauración, decisiones de diseño y limitaciones conocidas.
- [`docs/informe-tecnico.md`](docs/informe-tecnico.md) — resultados de pruebas, caracterización de latencia del modelo, análisis de cuello de botella.
