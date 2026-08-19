# Manual Técnico

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
