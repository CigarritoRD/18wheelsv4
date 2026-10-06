# Desplegar 18wheelers gratis: Render + Neon + R2

Actualizado: 5 de octubre de 2026. Esta versión permite empezar con un servicio
Render Free y una base de datos Neon Free. Las imágenes quedan en tu bucket R2
privado. La aplicación conserva la compresión WebP y los límites de subida.

## Qué conectarás

| Servicio | Guarda o ejecuta | Configuración |
|---|---|---|
| GitHub | Código de la aplicación | Repositorio privado |
| Render | Aplicación Python y página web | Un Web Service Free, Docker |
| Neon | Usuarios, trabajos, sesiones y cuotas | Un proyecto PostgreSQL Free |
| R2 | Imágenes comprimidas | Bucket privado, Standard |

**No despliegues el ZIP anterior en Render.** Necesitas esta versión con
`app/database.py` y `render.yaml`. El disco de Render Free es temporal. Esta
versión usa Neon para los datos y R2 para las fotos; `/data` solo contiene
archivos temporales. No necesitas comprar un disco persistente ni crear una
base de datos en Render.

La guía inicia una base nueva. Si ya tienes usuarios o trabajos en un archivo
`jobs.sqlite3`, conserva una copia: no se transfieren automáticamente a Neon.

## 1. Sube el código a GitHub

1. Descarga el ZIP actualizado y extráelo.
2. En GitHub crea un repositorio **privado**, por ejemplo `18wheelers-jobs`.
3. Sube el **contenido** de la carpeta `18wheelers-jobs-three-roles`.
4. En la raíz del repositorio debes ver `Dockerfile`, `docker_start.py`,
   `run.py`, `requirements.txt`, `render.yaml` y la carpeta `app`.

No subas solo el ZIP ni lo dejes dentro de otra carpeta. No subas `.env`, datos
reales, credenciales ni carpetas `data`, `backups` o `.venv`.

## 2. Crea la base de datos gratuita en Neon

1. Entra a https://console.neon.tech y crea una cuenta.
2. Elige **Free** y crea un proyecto llamado `18wheelers-jobs`.
3. Selecciona una región cercana a la de Render. Esta configuración propone
   **Oregon** para Render; usa US West/Oregon si Neon ofrece esa región.
4. Abre **Connect** en el proyecto. Elige la base de datos y el rol del proyecto.
5. Activa **Connection pooling** y copia la **connection string** PostgreSQL.

Su aspecto es:

```text
postgresql://USUARIO:CONTRASENA@HOST-pooler/BASE?sslmode=require
```

Copia solo la URL completa, sin `psql`, sin comillas, sin comandos ni bloques de
código. Conserva todos sus parámetros, incluido `sslmode=require` y, si aparece,
`channel_binding=require`. No la publiques ni me la envíes: contiene una contraseña.

La aplicación creará sus tablas al arrancar; no necesitas ejecutar SQL a mano.

## 3. Reúne los datos de R2

Si ya creaste el bucket y el token, usa los mismos. Necesitarás:

- Nombre del bucket, por ejemplo `18wheelers-photos`.
- Endpoint S3 completo: `https://TU_ACCOUNT_ID.r2.cloudflarestorage.com`.
- Access Key ID.
- Secret Access Key.

El endpoint debe ser el que muestra Cloudflare; si contiene `.eu`, `.us` o
`.fedramp`, consérvalo. No es la dirección del panel ni un dominio `r2.dev`.
El bucket debe ser **privado** y **Standard**. El token necesita permisos
**Object Read & Write**, limitados a ese bucket. No necesitas CORS para este flujo.
La guía `docs/R2_SETUP_ES.md` explica cómo crear el bucket y el token; sus pasos
de Railway corresponden únicamente a ese proveedor.

## 4. Crea el servicio en Render

### Opción recomendada: Blueprint

1. Entra a https://dashboard.render.com y crea una cuenta.
2. Selecciona **New → Blueprint** y conecta GitHub.
3. Autoriza el repositorio privado y selecciónalo.
4. Render leerá `render.yaml`. Comprueba que hay **un Web Service Free**.
5. Completa los cinco campos que solicita con tus datos de Neon y R2:

| Variable | Valor |
|---|---|
| `DATABASE_URL` | URL PostgreSQL completa y con pooling de Neon |
| `EW_R2_BUCKET` | Nombre exacto del bucket |
| `EW_R2_ENDPOINT_URL` | Endpoint S3 de Cloudflare |
| `EW_R2_ACCESS_KEY_ID` | Access Key ID |
| `EW_R2_SECRET_ACCESS_KEY` | Secret Access Key |

6. Confirma la creación/despliegue. El resto de las variables ya está en
   `render.yaml`. Los secretos se guardan en Render, no en GitHub.

### Si eliges New → Web Service

Conecta el mismo repositorio y configura:

| Campo | Valor |
|---|---|
| Name | `18wheelers-jobs` |
| Language / Runtime | **Docker** |
| Region | **Oregon** |
| Branch | La rama que contiene el código, normalmente `main` |
| Root Directory | Vacío, si subiste los archivos a la raíz |
| Dockerfile Path | `./Dockerfile` |
| Docker Command | Vacío: usa el comando incluido |
| Instance Type | **Free** |
| Health Check Path | `/health` |

Añade las cinco variables secretas de arriba y estas variables:

```text
EW_HOST=0.0.0.0
EW_DATA_DIR=/data
EW_SECURE_COOKIES=1
EW_PHOTO_STORAGE=r2
EW_R2_URL_TTL_SECONDS=60
```

Render proporciona `PORT`; no hace falta fijarlo manualmente. No añadas un
Build Command para Node ni ejecutes npm. No agregues un disco o una base Render
Postgres. Después, selecciona **Deploy Web Service**.

## 5. Abre la página y crea tu administrador

1. Espera a que Render indique que el servicio está activo.
2. Copia la dirección HTTPS del servicio, por ejemplo
   `https://18wheelers-jobs-xxxx.onrender.com`.
3. En **Logs**, busca `FIRST-TIME SETUP (private link)` y el enlace siguiente:
   `http://127.0.0.1:PUERTO/?setup_token=...`.
4. Sustituye **solo** `http://127.0.0.1:PUERTO` por tu dirección HTTPS de Render.
   Conserva `/?setup_token=...` completo.
5. Abre ese enlace privado y crea el administrador con una contraseña de
   al menos 12 caracteres. Comparte después la dirección normal, sin el token.

El token inicial queda en Neon y permanece igual si Render borra su disco.
Después del alta, la aplicación rechaza crear otro administrador por este método.

## 6. Verifica las conexiones

1. Crea un trabajo de prueba y sube una imagen.
2. Comprueba que aparece en la aplicación y como `.webp` en R2.
3. Abre **Team → Photo storage** como administrador y revisa el espacio ocupado.
4. Reinicia o vuelve a desplegar el servicio. Inicia sesión y verifica que
   siguen el trabajo y la imagen. El servidor nuevo debe usar la misma
   `DATABASE_URL`, bucket y prefijo R2.
5. Crea un técnico y un solicitante y prueba el flujo de asignación.

## Límites y costos

- Render Free se suspende después de 15 minutos sin tráfico; abrirlo de nuevo
  puede tardar alrededor de un minuto. Puede limitar o suspender el servicio
  si agotas la cuota o genera mucho tráfico hacia Neon/R2. No se recomienda
  como alojamiento de producción para un servicio crítico.
- Mantén **Free** como tipo de instancia y revisa las cuotas del panel. Si no
  hay un método de pago, al superar determinadas cuotas Render suspende los
  servicios o bloquea nuevas compilaciones en lugar de cobrar el excedente.
- Mantén Neon en **Free**. Sus límites pueden detener operaciones hasta que
  liberes recursos, se renueve la cuota o decidas actualizar el plan.
- R2 **sí puede cobrar excedentes**: su cuota gratis no es un límite de gasto.
  Los controles de la aplicación reducen el abuso, pero no garantizan una
  factura cero. Las alertas de presupuesto no detienen el consumo.

Se mantienen los límites existentes: 5000 MiB de fotos gestionadas por la app,
300 KiB por imagen comprimida, 100 fotos por trabajo, cuotas por usuario y
cuotas globales de solicitudes. Los originales no se conservan. Los límites
protegen las operaciones de la aplicación; no cubren accesos externos al
bucket, credenciales comprometidas ni la repetición de enlaces firmados.

## Problemas frecuentes

| Mensaje / problema | Qué revisar |
|---|---|
| `Render requires DATABASE_URL` | Añade la URL de Neon y vuelve a desplegar |
| `Render requires EW_PHOTO_STORAGE=r2` | Configura almacenamiento R2 y sus cuatro valores |
| `Cannot connect to PostgreSQL` | URL completa, contraseña, parámetros SSL, proyecto y cuota Neon |
| `Missing R2 configuration` / fallo de almacenamiento | Token Object Read & Write, bucket y endpoint exactos |
| La página espera al abrir | Puede ser el arranque de Render después de estar inactivo |
| No aparece FIRST-TIME SETUP | Busca logs de arranque; si ya existe un usuario, no se imprime otro enlace |
| Imágenes fallan después de cambiar de bucket/prefijo | Usa los valores con los que se subieron; cambiar env no mueve archivos |

No publiques logs con tokens ni capturas con secretos. Rota las credenciales
en el proveedor si las expones. El comando `admin.py backup` solo respalda
SQLite; para Neon usa `pg_dump` o las opciones de exportación del proveedor,
y respalda el bucket por separado.

## Referencias oficiales

- Render Free: https://render.com/docs/free
- Docker en Render: https://render.com/docs/docker
- Blueprint: https://render.com/docs/blueprint-spec
- Neon: https://neon.com/docs/get-started/connect-neon
- Planes Neon: https://neon.com/pricing
- R2: https://developers.cloudflare.com/r2/pricing/
