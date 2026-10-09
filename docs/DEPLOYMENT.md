# Shared access and deployment

This file describes the original single-server SQLite deployment. For the
recommended hosted layout using Supabase Postgres and private Cloudflare R2 photo
storage, use `CLOUD_DEPLOYMENT.md`.

## Current delivery state

The code, launchers, and standalone preview are complete. There is **no live public
URL** and no connection to an 18wheelers production account, company directory,
email system, or hosting provider. No domain, hosting account, or paid service was
created. The provided Dockerfile and reverse-proxy example are templates; they
have not been deployed or container-tested in this environment.

## Choose one server

All team members need to reach the same running application instance. A suitable
small setup is one Windows or Linux server with a persistent disk and a private
VPN, or a hosted server reached through an HTTPS reverse proxy. The server must
stay running. Do not distribute separate copies of the preview or SQLite database
as a synchronization strategy.

By default, `run.py` binds only to `127.0.0.1` to avoid exposing the application to
the network accidentally. The first-time setup URL printed by the launcher
includes a random private token. Complete setup yourself before sharing access.
If using an HTTPS hostname, substitute that hostname for the local address in the
setup URL and retain the `setup_token` parameter.

## Recommended public-facing layout

```text
Team browser -> HTTPS reverse proxy -> 127.0.0.1:8080 -> app + persistent data
```

Use a domain you control, valid TLS certificates, and a reverse proxy such as
Caddy or nginx. Do not forward the raw HTTP application port directly to the
internet. Restrict backend access with a firewall and do not run the app as root.

Example environment and startup on Linux:

```sh
export EW_DATA_DIR=/var/lib/18wheelers-jobs
export EW_SECURE_COOKIES=1
export EW_HOST=127.0.0.1
export PORT=8080
.venv/bin/python run.py --no-browser
```

Create the data directory first and give the dedicated app user read/write access.
Keep it outside the source repository. `EW_SECURE_COOKIES=1` means the browser
must reach the site through HTTPS; plain HTTP sign-in will not retain that cookie.
Do not enable secure cookies for the default plain-HTTP local-only trial.

Illustrative Caddyfile, to be reviewed by the hosting administrator:

```text
jobs.your-domain.example {
    reverse_proxy 127.0.0.1:8080
}
```

Replace the example hostname with a real DNS name you control. Certificate
issuance requires correct DNS and the network conditions required by your
certificate provider. Configure automatic app restarts, log rotation, monitoring,
regular backups, and a disk-space alert at the host level.

For private network access without a reverse proxy, `python run.py --host 0.0.0.0`
binds to the network. Team members would use the server's actual LAN address, not
`0.0.0.0` and not their own `127.0.0.1`. This alone is not secure remote deployment:
plain HTTP does not protect credentials or photos in transit. Prefer an HTTPS
endpoint even on a shared network, and limit access with firewall/VPN controls.

## Proxy and login-rate considerations

The launcher uses `proxy_headers=False`. This avoids trusting user-supplied
forwarded headers. Behind a proxy, the IP-based login limit will count requests
against the proxy's address (60 attempts per 15 minutes), while the account-based
limit remains 10 per 15 minutes. For a larger team, configure trusted proxy
handling narrowly, based on your actual network, or apply a reviewed rate limiter
at the proxy. Do not simply trust arbitrary X-Forwarded-For headers from the
internet. This is one reason to review a public deployment rather than opening a
port blindly.

No permissive CORS configuration is needed: the UI and API are served from the
same origin. Keep them together unless the authentication and CSRF design is
reviewed for a separate frontend domain.

## Optional container template

The Dockerfile uses a non-root app user and expects a persistent `/data` volume.
For a local-only container trial:

```sh
docker build -t 18wheelers-jobs .
docker volume create 18wheelers-data
docker run --rm --name 18wheelers-jobs \
  -p 127.0.0.1:8080:8080 \
  -v 18wheelers-data:/data \
  18wheelers-jobs
```

For bind-mounted directories, make sure UID 10001 can write to the host directory.
Use an HTTPS reverse proxy and `EW_SECURE_COOKIES=1` before remote access. Back up
the mounted volume, not the disposable container. Do not run multiple containers
against separate volumes and expect shared jobs.

## Operational checklist

Before a pilot: use a private admin password, create only necessary team
accounts, verify that technicians see only assigned work and requesters see only
their own submissions, upload test images,
check the actual phones your staff use, and rehearse backup/restore. Review
privacy and retention practices for job photos. Confirm whether retaining only
resized JPEGs is appropriate; the app does not preserve originals.

Before broader deployment: review the code and host security, patch dependencies,
use HTTPS, ensure the data disk is persistent, establish recovery procedures,
monitor free disk space, and test your expected workload. This package is not an
independently audited production service.

Official background:
https://fastapi.tiangolo.com/deployment/manually/
