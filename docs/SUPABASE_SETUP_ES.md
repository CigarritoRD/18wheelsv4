# Supabase + Cloudflare R2 en Render

La versión desplegada conserva los tres roles, la compresión WebP y las cuotas
persistentes de fotos del repositorio. Supabase se usa como PostgreSQL; las
cuentas y sus permisos siguen administrados por FastAPI, no por Supabase Auth.

## Estado de infraestructura

- Proyecto Supabase: `kiuvljeudopvaumkkrrd`, región `us-east-1`.
- Migraciones en `supabase/migrations`: diez tablas en `app_private`, todas con
  RLS y sin permisos para `anon`, `authenticated` o `PUBLIC`.
- Bucket R2 existente: `18wheelers-photos`, acceso público deshabilitado.
- Servicio Render existente: `18wheelers-jobs` / `one8wheelers-jobs.onrender.com`.

## Variables de Render

Reemplaza `DATABASE_URL` de Neon por la conexión **Session pooler** de Supabase:

```text
postgresql://postgres.kiuvljeudopvaumkkrrd:ENCODED_PASSWORD@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require
```

`ENCODED_PASSWORD` es la contraseña real del proyecto, codificada como componente
de URL. No publiques la contraseña, la cadena completa ni las claves R2 en GitHub.

El Blueprint define `EW_DB_SCHEMA=app_private`. En ese modo el servidor verifica
las migraciones existentes y no crea tablas en `public` durante el arranque.

Las variables de imágenes conservan los nombres usados en este repositorio:

```text
EW_PHOTO_STORAGE=r2
EW_R2_BUCKET=18wheelers-photos
EW_R2_ENDPOINT_URL=https://6812e9c175fd943a1681cebca25ff7be.r2.cloudflarestorage.com
EW_R2_ACCESS_KEY_ID=<secret in Render>
EW_R2_SECRET_ACCESS_KEY=<secret in Render>
EW_R2_URL_TTL_SECONDS=60
EW_SECURE_COOKIES=1
```

No habilites el acceso público del bucket. FastAPI comprueba los permisos de
cada foto antes de emitir un enlace firmado de 60 segundos. Los enlaces firmados
son credenciales temporales: no los compartas ni registres en logs.

## Verificación pendiente del despliegue

Tras guardar las variables y desplegar, `/health` debe devolver `status: ok`;
esta comprobación también ejecuta `SELECT 1` en la base configurada. Verifica
después el alta inicial de administrador, los tres roles, una carga real de
imagen y que los datos persistan al reiniciar. Las pruebas locales usan SQLite y
un R2 simulado; no equivalen a esa comprobación de producción.
