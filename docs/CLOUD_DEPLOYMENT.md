# Despliegue con Supabase y Cloudflare R2

> **Fuente del despliegue:** esta carpeta es el proyecto que se publica.
> `../render-repository` es únicamente la copia Git usada para llevar este código
> al repositorio `CigarritoRD/18wheelsv4`, rama `main`, conectado a Render.
> La versión anterior se conserva en el historial Git y en
> `../render-before-local-deploy.bundle`. No copiar `.env`, `data/`, `.venv/` ni
> `.tmp/`. Esta aplicación acepta las variables `EW_R2_*` ya guardadas en Render
> como alternativas a `R2_*`. El bucket existente es `18wheelers-photos`, privado.
> `EW_DB_SCHEMA=app_private` puede conservarse; esta versión fija ese esquema en
> su adaptador Postgres. Las tablas adicionales de cuotas no se eliminan, pero
> esta edición no implementa las cuotas ni el procesamiento WebP del repositorio
> anterior: procesa JPEG y sirve las fotos después de comprobar permisos.

Esta versión mantiene FastAPI como la única API de la aplicación:

```text
Navegador -> HTTPS -> FastAPI -> Supabase Postgres
                           \-> Cloudflare R2 privado
```

Supabase guarda usuarios, sesiones, trabajos, comentarios y metadatos de fotos.
Cloudflare R2 guarda los JPEG procesados. El navegador nunca recibe credenciales
de Supabase o R2: solicita `/photos/{id}` y FastAPI comprueba primero el rol y el
acceso al trabajo. La autenticación continúa siendo la autenticación propia del
proyecto; no se ha cambiado a Supabase Auth.

Supabase no ejecuta este servidor Python. Despliega el contenedor en un servicio
para aplicaciones web (Render, Railway, Fly.io, Cloud Run u otro equivalente) y
configura allí las variables de entorno descritas abajo.

## 1. Crear y preparar Supabase

Configurado el 8 de octubre de 2026: **18wheelers-jobs**, proyecto
`kiuvljeudopvaumkkrrd`, región `us-east-1`. Las migraciones `create_jobs_schema` y
`add_foreign_key_indexes` ya están aplicadas. Las siete tablas tienen RLS y el
esquema `app_private` no permite acceso a `anon` ni a `authenticated`.

Panel: https://supabase.com/dashboard/project/kiuvljeudopvaumkkrrd

La cadena Session pooler se comprobó en el panel. Falta sustituir
`ENCODED_PASSWORD` por la contraseña de base de datos al configurar el secreto
`DATABASE_URL` en el servidor:

```text
postgresql://postgres.kiuvljeudopvaumkkrrd:ENCODED_PASSWORD@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require
```

La verificación SQL en la base real pasó: inserciones en las siete tablas,
relaciones, cambio de estado con versión y contador de intentos de login. Las
filas de prueba se revirtieron; no se crearon cuentas ni trabajos permanentes.
La conexión desde FastAPI aún necesita configurar `DATABASE_URL` con el secreto.

Los pasos siguientes son para reproducir la configuración en un proyecto nuevo.

1. Crea un proyecto de Supabase y conserva la contraseña de base de datos en un
   gestor de secretos.
2. Desde la raíz del repositorio, autentica y vincula el CLI:

   ```sh
   supabase login
   supabase link --project-ref TU_PROJECT_REF
   supabase db push
   ```

3. En el panel de Supabase abre **Connect** y copia la conexión **Session pooler**
   (puerto `5432`). Añade `?sslmode=require` si la cadena no trae parámetros.
   Codifica caracteres reservados de la contraseña (`@`, `#`, `?`, `%`, espacios)
   antes de insertarla en la URL.

No uses el transaction pooler del puerto `6543`: este servidor es persistente y
mantiene un pool pequeño de conexiones. Las tablas se crean en `app_private`, no
en `public`; por eso no están expuestas a las APIs REST/GraphQL de Supabase. RLS
está activado sin políticas públicas como protección adicional. FastAPI conecta
como propietario de las tablas y aplica los permisos de Admin, Technician y
Requester.

## 2. Crear el bucket privado de Cloudflare R2

1. En Cloudflare abre **R2 Object Storage** y crea un bucket, por ejemplo
   `18wheelers-job-photos`.
2. Déjalo privado. No habilites `r2.dev` ni un dominio público.
3. Crea una API Token de R2 limitada a lectura y escritura de objetos en ese
   bucket. Guarda el Access Key ID y el Secret Access Key; el secreto se muestra
   una sola vez.
4. El endpoint S3 tiene este formato:

   ```text
   https://ACCOUNT_ID.r2.cloudflarestorage.com
   ```

No hace falta configurar CORS porque las cargas y descargas pasan por FastAPI.

## 3. Variables del servicio FastAPI

Configura como secretos del hosting:

```text
DATABASE_URL=postgresql://postgres.kiuvljeudopvaumkkrrd:ENCODED_PASSWORD@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require
EW_DB_POOL_SIZE=5
EW_SETUP_TOKEN=un-secreto-aleatorio-de-al-menos-32-caracteres
EW_SECURE_COOKIES=1
R2_ENDPOINT_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET=18wheelers-job-photos
EW_HOST=0.0.0.0
PORT=8080
```

Usa `.env.example` únicamente como referencia. No subas un `.env` real ni pegues
secretos en el repositorio. Para generar `EW_SETUP_TOKEN` puedes usar un gestor
de contraseñas o `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

El servicio se construye con el `Dockerfile` incluido y arranca con:

```text
python run.py --no-browser
```

Configura `/health` como health check y publica el puerto indicado por `PORT`.
El hosting debe terminar TLS/HTTPS antes de enviar tráfico a FastAPI.

## 4. Crear el primer administrador

Cuando el despliegue esté sano, abre:

```text
https://TU_DOMINIO/?setup_token=EL_VALOR_DE_EW_SETUP_TOKEN
```

Crea el primer administrador. Luego rota o elimina `EW_SETUP_TOKEN` en el hosting
y vuelve a desplegar. El endpoint de setup rechaza nuevos administradores una vez
que existe el primero, pero el token sigue siendo un secreto y no debe conservarse
sin necesidad.

## 5. Verificación antes de invitar al equipo

- `/health` responde `{"status":"ok"}`.
- Un Admin puede crear un Requester y un Technician.
- El Requester solo ve sus solicitudes.
- El Technician solo ve trabajos asignados.
- Una foto cargada aparece en el bucket bajo `photos/`, pero no abre mediante una
  URL pública de Cloudflare.
- Al cerrar sesión, `/photos/{id}` responde `401`.
- Tras reiniciar o reemplazar el contenedor, trabajos y fotos siguen disponibles.

## Copias de seguridad

El comando local `admin.py backup` solo respalda instalaciones SQLite. En cloud,
usa las copias de seguridad/PITR del plan de Supabase y una política separada para
R2 (retención, versionado externo o copia a otro destino). Una copia de Postgres
sin los objetos de R2 no es una recuperación completa. Prueba periódicamente una
restauración de ambos componentes.

## Datos de una instalación SQLite existente

No apuntes una instalación con datos a `DATABASE_URL` esperando una migración
automática. El esquema cloud se inicia vacío. Antes de importar datos reales,
haz una copia con `admin.py backup`, detén el servidor local y planifica una
migración controlada de las filas y de `data/uploads/`. Las sesiones y los intentos
de login no deben migrarse; todos deben iniciar sesión nuevamente.
