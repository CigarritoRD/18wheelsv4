# Desplegar 18wheelers Jobs: GitHub + Railway + Cloudflare R2

Esta guía sirve para la entrega actualizada que incluye docker_start.py.
No necesitas instalar Python en tu computadora para desplegarla.

## 1. Preparar GitHub

1. Descarga y extrae el ZIP actualizado.
2. Crea un repositorio privado en GitHub llamado `18wheelers-jobs`.
3. Sube el CONTENIDO de la carpeta extraída, no el archivo ZIP. En la raíz del
   repositorio deben verse `Dockerfile`, `docker_start.py`, `requirements.txt`,
   `run.py`, `admin.py` y la carpeta `app`.
4. Puedes usar GitHub Desktop o Git si prefieres trabajar con una carpeta local.
   Si usas la web, abre Add file → Upload files, arrastra los archivos y carpetas
   interiores y confirma con Commit changes.
5. No subas datos reales, .env, claves ni copias de la base de datos.

## 2. Crear el bucket de fotos

1. En Cloudflare abre R2 Object Storage y revisa sus condiciones de facturación.
   La cuota gratuita no garantiza una factura de $0.
2. Crea `18wheelers-photos` con almacenamiento Standard.
3. Mantén desactivados Public Development URL/r2.dev y cualquier dominio público.
4. En R2 Overview, busca Account Details → API Tokens → Manage.
5. Crea un token para R2 con permiso Object Read & Write y limita el alcance a
   ese bucket. No hace falta darle permiso para administrar todos los buckets.
6. Guarda Access Key ID y Secret Access Key. El Secret solo se muestra una vez.
7. Copia el endpoint S3 que muestra Cloudflare, normalmente
   `https://TU_ACCOUNT_ID.r2.cloudflarestorage.com`. Si elegiste una jurisdicción,
   copia su endpoint exacto (eu, us o fedramp), sin modificarlo.

## 3. Crear el servicio de Railway

1. Accede a Railway y elige New Project → Deploy from GitHub repo.
2. Autoriza el acceso al repositorio necesario y selecciona `18wheelers-jobs`.
3. Railway detectará el Dockerfile. No necesitas configurar un Build Command
   o Start Command personalizado; el Dockerfile incluye ambos pasos.
4. Antes de crear cuentas o introducir datos, configura el volumen y variables.
   El primer intento de despliegue puede reiniciarse al aplicar estos cambios.

## 4. Crear el volumen persistente

1. En el proyecto añade un Volume al servicio de la app (Add/New → Volume;
   también puedes usar el menú del servicio o la paleta de comandos).
2. Establece Mount Path en `/data`.
3. Guarda/aplica los cambios. El volumen debe estar conectado a ESE servicio.
4. Mantén una sola instancia/réplica mientras utilices SQLite.

El volumen guarda usuarios, trabajos, sesiones y el token inicial. R2 solo guarda
las fotos. El nuevo docker_start.py prepara el propietario del volumen antes de
bajar a UID 10001 y arrancar FastAPI. No necesitas RAILWAY_RUN_UID=0 ni ejecutar
el servidor web como root. No cambies el Start Command por run.py directamente:
el paso de preparación de permisos debe ejecutarse primero.

## 5. Conectar mediante las variables

Abre el servicio → Variables y añade las siguientes. Puedes usar el editor de
variables en formato KEY=VALUE si Railway lo muestra. Reemplaza los valores de
las tres claves indicadas; no dejes los textos de ejemplo.

```dotenv
EW_PHOTO_STORAGE=r2
EW_DATA_DIR=/data
EW_HOST=0.0.0.0
PORT=8080
EW_SECURE_COOKIES=1
EW_R2_ENDPOINT_URL=PEGA_AQUI_EL_ENDPOINT_S3
EW_R2_BUCKET=18wheelers-photos
EW_R2_ACCESS_KEY_ID=PEGA_AQUI_EL_ACCESS_KEY_ID
EW_R2_SECRET_ACCESS_KEY=PEGA_AQUI_EL_SECRET_ACCESS_KEY
EW_R2_URL_TTL_SECONDS=60
EW_PHOTO_TOTAL_LIMIT_MB=5000
EW_PHOTO_MAX_STORED_KB=300
EW_PHOTO_MAX_DIMENSION=1600
EW_PHOTO_WEBP_QUALITY=80
```

Guarda las credenciales solo en Railway, como valores secretos/sellados si esa
opción aparece. No las pegues en GitHub, el chat o capturas. El prefijo por defecto
es `18wheelers/photos`. Los demás límites conservan los valores seguros de la app.
No necesitas configurar la conexión a SQLite: se crea automáticamente en `/data`.
Tampoco necesitas CORS para mostrar las fotos mediante la interfaz de esta app.

Aplica los cambios y redespliega. En Settings → Deploy puedes configurar
Healthcheck Path como `/health`. El servicio debe arrancar sin errores de permisos.

## 6. Obtener la dirección web

1. En Settings → Networking → Public Networking pulsa Generate Domain.
2. Si te pide Target Port, coloca `8080`.
3. Abre la URL HTTPS que Railway genere. No uses la dirección 127.0.0.1 del log.
   Railway sirve la app y la interfaz bajo una misma URL.

## 7. Crear el primer administrador

1. Abre los logs del primer arranque exitoso.
2. Busca `FIRST-TIME SETUP (private link)` y el enlace local con `setup_token`.
3. Sustituye SOLO `http://127.0.0.1:8080` por tu URL HTTPS de Railway.
   Conserva `/?setup_token=...` exactamente como apareció.
4. Abre ese enlace en privado y crea tu nombre, email y contraseña de administrador.
5. Completa este paso antes de compartir la URL con tu equipo. No compartas el
   token ni capturas del enlace. Luego puedes crear usuarios desde Team.

Ejemplo de estructura, con un token ficticio:
`https://TU_APP.up.railway.app/?setup_token=TOKEN_PRIVADO_DEL_LOG`

## 8. Comprobar las conexiones

1. Crea un trabajo de prueba y sube una foto no sensible.
2. En R2 comprueba que apareció un objeto .webp bajo `18wheelers/photos/`.
3. En la app comprueba que se muestra correctamente.
4. En Team → Photo storage comprueba el espacio usado.
5. Redespliega sin eliminar el volumen: deben conservarse usuario, trabajo y foto.
6. Prueba una cuenta que no tenga permiso para ese trabajo.

Si la app abre pero las fotos fallan, revisa endpoint, bucket, claves y permisos.
Un 429 indica un límite de solicitudes; un 413 indica capacidad o cantidad máxima;
un 503 al subir/leer fotos puede indicar problema de conexión/configuración de R2.
No cambies o borres el volumen para resolver un error de conexión.

Railway y Cloudflare tienen facturación independiente. Revisa los créditos,
consumo y alertas de ambos; los límites de esta app no son un tope de facturación.

Referencias verificadas:
- https://docs.railway.com/volumes
- https://docs.railway.com/builds/dockerfiles
- https://docs.railway.com/networking/public-networking
- https://developers.cloudflare.com/r2/api/tokens/

# Detalles de R2 y límites incluidos

# Imágenes privadas en Cloudflare R2 (opcional)

## Estado de esta entrega

El código soporta R2, pero sigue usando almacenamiento local por defecto.
No se ha creado ningún bucket, introducido una tarjeta, generado claves reales
ni desplegado la aplicación. Las pruebas utilizan un simulador y el SDK real
con respuestas simuladas; falta verificar una subida y lectura en una cuenta real.

## Antes de activar R2: facturación

R2 Standard incluye una cuota gratuita mensual de 10 GB-mes,
1 millón de operaciones clase A y 10 millones de operaciones clase B.
El exceso se cobra según consumo; no es un servicio con coste máximo de $0.
Las alertas de presupuesto notifican, pero NO detienen ni limitan el consumo.
La cuota gratuita no se aplica a Infrequent Access.

Si necesitas probar sin tarjeta ni cargos automáticos, mantén
`EW_PHOTO_STORAGE=local` o adapta el almacenamiento a Supabase Free.
Esta entrega todavía NO implementa Supabase Storage.

## Configuración opcional de R2

1. En Cloudflare, abre R2 Object Storage. Revisa y acepta la facturación solo
   si quieres utilizar este proveedor.
2. Crea un bucket llamado `18wheelers-photos` con almacenamiento Standard.
3. Mantén desactivado el acceso público: sin dominio público ni URL r2.dev.
4. Genera credenciales S3 con permiso **Object Read & Write**, limitadas a
   este bucket. Guarda el Access Key ID y Secret Access Key de forma privada.
5. Copia el endpoint S3 exacto que muestra Cloudflare. Es una URL HTTPS
   con tu Account ID, normalmente `https://ACCOUNT_ID.r2.cloudflarestorage.com`.
6. En las variables del servicio de Railway configura:

| Variable | Valor |
| --- | --- |
| `EW_PHOTO_STORAGE` | `r2` |
| `EW_R2_ENDPOINT_URL` | Endpoint S3 copiado de Cloudflare |
| `EW_R2_BUCKET` | `18wheelers-photos` |
| `EW_R2_ACCESS_KEY_ID` | Access Key ID; valor secreto |
| `EW_R2_SECRET_ACCESS_KEY` | Secret Access Key; valor secreto |
| `EW_R2_PREFIX` | `18wheelers/photos` |
| `EW_R2_URL_TTL_SECONDS` | `300` |
| `EW_DATA_DIR` | `/data` |
| `EW_SECURE_COOKIES` | `1` para HTTPS |

No incluyas las claves en GitHub, capturas, mensajes o código JavaScript.
`.env.example` solo documenta las variables: no carga un archivo `.env`.

## Railway sigue necesitando un volumen

Monta el volumen persistente en `/data`. SQLite, las sesiones, usuarios,
trabajos y el token inicial siguen almacenados ahí. R2 separa las fotos;
no convierte toda la aplicación en stateless ni reemplaza los backups de SQLite.
Usa una sola instancia de la aplicación mientras utilices SQLite.

Despliega el Dockerfile existente y configura el puerto mediante `PORT`.
Antes de usar datos reales, prueba la configuración con imágenes de prueba.
No se garantiza que los créditos del plan gratuito de Railway cubran tu uso.

## Cómo funciona

- El servidor valida y convierte las imágenes nuevas a WebP, sin metadatos EXIF/XMP. Las fotos JPEG anteriores conservan su formato.
- Las fotos nuevas van a R2 cuando `EW_PHOTO_STORAGE=r2`.
- En SQLite se guarda una referencia `r2:18wheelers/photos/NOMBRE.webp` y su tamaño comprimido.
- El usuario pide `/photos/ID`; la app verifica sus permisos antes de responder.
- Para R2 responde con un enlace firmado que vence a los cinco minutos.
  Quien reciba ese enlace puede usarlo hasta que venza.
- La política de imágenes del navegador permite únicamente el endpoint R2
  configurado. No necesitas CORS para mostrar imágenes mediante `<img>`.
- Las fotos locales anteriores siguen funcionando desde `/data/uploads`.
  No se migran automáticamente; conserva ese directorio y sus backups.
- No cambies el bucket o el prefijo después de subir fotos sin una migración.
- Para seguir accediendo a fotos de R2, debes mantener su configuración activa.

## Verificación real pendiente

1. Accede como administrador y crea un trabajo de prueba.
2. Sube una imagen y comprueba que aparece en el bucket privado.
3. Comprueba que se ve en la app y no se copia a `/data/uploads`.
4. Comprueba que un usuario sin acceso al trabajo no puede obtener el enlace.
5. Borra la imagen desde la app y comprueba que desaparece del bucket.
6. Redespliega y confirma que siguen los usuarios, trabajos e imágenes.

R2 y SQLite no comparten una transacción. La app intenta limpiar las imágenes
si falla una subida múltiple y conserva el registro si falla el borrado remoto.
Un corte de proceso o un fallo durante la limpieza puede dejar objetos huérfanos;
revisa los backups y objetos si ocurre. El borrado remoto y el commit de SQLite
tampoco son atómicos: un fallo excepcional de commit puede dejar un registro
que apunte a una imagen ya eliminada.

## Referencias

- https://developers.cloudflare.com/r2/pricing/
- https://developers.cloudflare.com/billing/manage/budget-alerts/
- https://developers.cloudflare.com/r2/api/tokens/
- https://developers.cloudflare.com/r2/examples/aws/boto3/
- https://supabase.com/pricing
- https://supabase.com/docs/guides/platform/billing-faq


## Límites incluidos para evitar llenar el bucket desde la app

Todos se aplican en el servidor, incluso si alguien omite la interfaz.
Solo los usuarios autenticados y autorizados para el trabajo pueden subir fotos.
La aplicación conserva el control de CSRF y roles existente.

| Protección | Valor inicial | Variable |
| --- | --- | --- |
| Espacio de fotos, incluyendo reservas | 5000 MiB (aprox. 5.24 GB) | `EW_PHOTO_TOTAL_LIMIT_MB` |
| Tamaño máximo de imagen comprimida | 300 KiB | `EW_PHOTO_MAX_STORED_KB` |
| Dimensión inicial máxima | 1600 px de ancho o alto | `EW_PHOTO_MAX_DIMENSION` |
| Calidad WebP inicial | 80 | `EW_PHOTO_WEBP_QUALITY` |
| Fotos por trabajo | 100 | `EW_PHOTO_MAX_PER_JOB` |
| Solicitudes de subida por usuario/minuto | 3 | `EW_UPLOAD_REQUESTS_USER_MINUTE` |
| Solicitudes de subida globales/minuto | 20 | `EW_UPLOAD_REQUESTS_GLOBAL_MINUTE` |
| Fotos intentadas por usuario/día | 100 | `EW_UPLOAD_PHOTOS_USER_DAY` |
| Fotos intentadas globales/día | 500 | `EW_UPLOAD_PHOTOS_GLOBAL_DAY` |
| Solicitudes de subida globales/30 días | 50000 | `EW_UPLOAD_REQUESTS_GLOBAL_MONTH` |
| Solicitudes de lectura por usuario/minuto | 120 | `EW_PHOTO_READS_USER_MINUTE` |
| Solicitudes de lectura globales/30 días | 500000 | `EW_PHOTO_READS_GLOBAL_MONTH` |

Los contadores usan ventanas fijas UTC. Las ventanas de 30 días NO son el ciclo
de facturación de Cloudflare. Los límites de solicitudes incluyen intentos
fallidos después de la autorización. Los límites diarios de fotos incluyen
archivos intentados y fallos; borrar fotos no devuelve esa cuota diaria.

El límite de tamaño de entrada continúa en 12 MiB por archivo y 32 MiB por
solicitud. Se permiten hasta ocho imágenes por solicitud. Solo se procesan
hasta dos subidas simultáneas por proceso; las demás reciben 429 con Retry-After.
La compresión se ejecuta fuera del bucle del servidor. Se prueban hasta seis
combinaciones de calidad/resolución para respetar los 300 KiB, y se rechaza la
foto si no cabe. Los originales no se conservan: guarda aparte cualquier
original que necesites para evidencias o documentos detallados.

La app utiliza reservas en SQLite con transacciones `BEGIN IMMEDIATE`.
Dos subidas paralelas no pueden reservar el mismo espacio disponible.
El tamaño se cuenta DESPUÉS de comprimir y ANTES de subir a R2.
La reserva se sustituye por los tamaños de las fotos al confirmar los registros.
Los contadores y reservas sobreviven a reinicios. Una reserva sin resolver no
vence automáticamente: así no se libera espacio que pueda corresponder a
objetos huérfanos después de una caída. El administrador debe contrastar
SQLite con R2, resolver esos objetos y luego liberar la reserva, sin eliminar
reservas de subidas todavía activas.

El administrador puede consultar el uso desde Team → Photo storage.
También existe el endpoint autenticado solo para admin `/api/storage/usage`.
Cambiar límites se hace mediante las variables del servidor y un redespliegue.
Las fotos antiguas locales se contabilizan al iniciar. Si existen fotos cuyo
tamaño no puede determinarse, las nuevas subidas se bloquean con 409 hasta
reconciliar los tamaños. No ejecutes varias réplicas de SQLite en discos separados.

## Lo que estos límites NO garantizan

- Se cuenta el espacio gestionado por ESTA app. No se incluyen archivos subidos
  manualmente, otros buckets o apps, versiones externas u objetos desconocidos.
  Utiliza un bucket exclusivo y no subas fotos por fuera del flujo de la app.
- Si alguien obtiene las credenciales de R2, puede saltarse los límites de la app.
- Un enlace firmado de lectura puede reutilizarse directamente contra R2 hasta
  que venza. Esa reutilización no pasa por los contadores de FastAPI.
- R2 también factura operaciones. Los reintentos del SDK y las lecturas directas
  pueden generar más operaciones que las solicitudes contabilizadas por la app.
- Estos controles no mitigan todo ataque de red o agotamiento del servidor.
  Los límites en el hosting/proxy son una capa adicional para tráfico abusivo.
- Un límite de subida reduce el riesgo de gasto; NO es un tope de facturación
  de Cloudflare ni una promesa de coste $0. Configura alertas y revisa el consumo.
- El backup local de `admin.py` NO copia los objetos de R2. Respáldalos por separado.

Para acortar la ventana de reutilización puedes poner
`EW_R2_URL_TTL_SECONDS=60` en Railway. El valor inicial sigue siendo 300.
