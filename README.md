# 18wheelers Jobs - Three-role edition

A working small-team web app for assigning jobs, documenting work with photos,
and tracking progress. Updated October 5, 2026 with Admin, Technician, and Requester roles.

**This package is not a hosted website.** The full app needs one running server.
The included demonstration is a different, local-only way to try the interface.
No company files, employee roster, or production records were imported.

## Deploy on Render Free with Supabase and R2

Follow **[the Supabase deployment guide in Spanish](docs/SUPABASE_SETUP_ES.md)**. This package
now supports PostgreSQL through `DATABASE_URL`, with persistent users, jobs,
sessions, setup token, photo counters and capacity reservations. Keep R2 private.
`render.yaml` defines one Free Docker web service and requests secrets in Render.
No persistent disk or Render database is needed. Render refuses to start with
local SQLite or local photo storage, to prevent losing data on an ephemeral disk.

Without `DATABASE_URL`, local usage continues to use SQLite. Existing SQLite
files are not automatically imported into Supabase; this guide starts a new database.

## Try the interface immediately

Open **18wheelers-preview.html** in Chrome, Edge, Safari, or Firefox. There is no
installation for the preview. It contains fictional sample jobs and clearly
labeled illustrations, and supports job creation, assignment, photo uploads,
status changes, comments, search, filters, and archive/restore. Use the **Admin**, **Technician**, and **Requester** buttons to try each view.
The separately supplied `18wheelers-three-role-preview.html` is the same preview.
This edition uses separate local demo storage; it does not migrate old preview edits.

The preview stores its changes only in that browser's local storage. It is not a
shared database, and it does not authenticate accounts. Do not enter real
passwords or confidential information in it. Browser restrictions or storage
quotas can prevent saving; the preview displays a saving error rather than
silently claiming success. Reset demo removes the local example data and restores
the samples. Modern desktop browsers generally allow opening the HTML directly;
managed or restricted browsers may require serving it from a local web server.

## Start the full application on Windows

1. Install **Python 3.11 or newer**, including the option **Add python.exe to PATH**.
   The app was tested with Python 3.13.5. The official installer is at
   https://www.python.org/downloads/.
2. Extract the entire ZIP to a folder you control. Do not run inside the ZIP.
3. Double-click **start_windows.bat**. The first run creates a virtual environment
   and installs the packages in `requirements.txt`, so it requires internet access.
4. Your browser opens the private first-time setup link. Enter your name, email,
   and a password with at least 12 characters. This creates the first admin.
   No default password or real sample accounts are installed.
5. Open **Team**, create an account for each person, and choose **Admin**,
   **Technician**, or **Requester**. New accounts default to Requester. Share
   temporary passwords privately; each person must change theirs on first sign-in.
6. Requesters use **New request** to submit an issue with photos. Admins open
   the request, choose **Edit job details**, and assign an active Technician.
   Admins can also create jobs directly with **New job**.

Keep the server window open while using the application. Close it with Ctrl+C.
Run the same launcher to reopen the app later; your data remains in `data/`.
After initial setup, the local address is **http://127.0.0.1:8080**.

The local address works only on the computer running the server. It is not an
internet address that you can send to employees. Shared access is explained in
`docs/DEPLOYMENT.md`.

If the browser does not open automatically, copy the setup link shown in the
server window. The first-time setup token is private; do not share it. If port
8080 is occupied, run `.venv\Scripts\python.exe run.py --port 8081`.

## macOS / Linux

With Python 3.11 or newer installed:

```sh
sh start_mac_linux.sh
```

Or run manually:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

Some Linux distributions require installing the distribution's `python3-venv`
package before creating the virtual environment.

## Three user levels

| Capability | 1. Admin | 2. Technician | 3. Requester |
| --- | --- | --- | --- |
| View jobs, photos, and history | All jobs | Currently assigned jobs only | Own submitted requests only |
| Create jobs / requests | Yes | No | Yes, starts New and unassigned |
| Edit job details, priority, due date | Yes | No | No; add a correction as a comment |
| Assign / reassign work | Active technicians only | No | No |
| Change status | All available statuses | In Progress, On Hold, Completed | No |
| Upload Before / General photos | Yes | Assigned jobs | Own requests |
| Upload After photos | Yes | Assigned jobs | No |
| Comment on jobs | Yes | Assigned jobs | Own requests |
| View archived history | All jobs | Assigned jobs | Own requests |
| Archive, restore, delete photos | Yes | No | No |
| Create accounts, change roles, reset passwords | Yes | No | No |
| Export job register as CSV | Yes | No | No |
| Change own password | Yes | Yes | Yes |

Archived jobs are read-only until an admin restores them. All comments and photos
on a job are visible to everyone authorized for that job; there is no private
internal-notes channel. A requester cannot browse other people's requests, and
an unassigned technician cannot browse the request queue. There is no public or
anonymous request submission: an admin must create the Requester account first.

### Workflow

**Requester submits -> New -> Admin assigns -> Assigned -> Technician works ->
In Progress -> Completed.** On Hold is also available.

A request can include a title, issue description, truck/unit, location, category,
requested priority, requested due date, and reference photos. The requester cannot
choose a technician or set the status. The admin can revise priority and due date.
After submission, the requester adds corrections or extra context as comments;
only the admin edits the job fields. The original submitter remains attached to
the job and is shown as **Submitted by**.

Categories remain Maintenance, Inspection, Delivery, Yard, Office, and Other.
There is one assigned technician per job. A technician can reopen their completed
job by choosing In Progress or On Hold. Completion does not require a formal
admin or requester approval/signature in this edition.

Admins see all job totals. Technicians see totals for their assigned work;
requesters see totals for their own requests. Dates render in the browser's local
time; due dates are calendar dates, not deadline times. New requests notify admins
inside the app. Assignments and status changes notify the relevant participants;
comments and uploads also generate in-app updates. Notifications require opening
the app; there are no SMS, email, or mobile push messages.

The dashboard refreshes about every 30 seconds when visible and not being edited.
Open dialogs are not automatically replaced. Concurrent edits to job details are
rejected with a reload instruction, rather than silently overwriting another edit.

### Existing installations

Read **docs/UPGRADE_THREE_ROLES.md** before upgrading. Stop the old server and make
a full backup first. This edition migrates the old `employee` role to `technician`
and retains `admin` as `admin`. IDs, passwords, jobs, photos, comments, and history
are preserved by the migration. Existing sessions are cleared, so everyone signs
in again. Create new Requester accounts or deliberately change the appropriate
accounts in Team. No existing employee is guessed to be a requester.

## Photos

The full app accepts **JPG, PNG, and WebP**. HEIC/HEIF images need conversion to JPG
first; this package does not include a HEIC decoder. Video, PDF attachments, and
other documents are not supported.

- Up to 8 photos per upload batch.
- Up to 12 MB per individual file, 30 MB selected per browser batch, and a
  32 MB total request limit on the server.
- Images over 24 megapixels are rejected. Resize them first.
- Uploaded files are decoded, orientation-corrected, resized to a maximum
  1600-pixel long edge initially, and re-encoded as WebP (up to 300 KiB by default). The server may reduce dimensions further to fit the limit.
- Embedded metadata, including GPS information, is removed by re-encoding.
- The uploaded original is not retained. Keep separate originals if evidence
  preservation or full-resolution images are necessary for your business.
- Before, After, and General labels organize the photos.
- Photos use private local storage or a private Cloudflare R2 bucket and require job authorization to view. Upload quotas apply on the server; see docs/R2_SETUP_ES.md.

The standard phone file chooser can offer the camera or photo library; the exact
choices depend on the device and browser. Direct camera APIs are not required.
No physical iPhone or Android device was available for testing.

## Security and accounts

The server enforces permissions independently of the browser. Passwords use salted
PBKDF2-SHA256 with 600,000 iterations. Session cookies are opaque, HttpOnly, and
SameSite=Lax; the database stores a hash of the session token. Sessions expire
after 12 hours; pre-login sessions after 30 minutes. Password changes and resets
revoke older sessions. Mutations require a per-session CSRF token.

Login throttling is persisted in the database: 10 attempts per account and 60 attempts
per connecting IP in a 15-minute window. When behind a reverse proxy, the built-in
launcher intentionally does not trust forwarded client-IP headers; the IP limit
may therefore apply across the proxy. See the deployment notes for implications.

The database and uploads are outside the public static directory. The app adds
content-security, anti-framing, and no-sniff headers, and protects CSV reports
against common spreadsheet formula injection. Admins cannot deactivate themselves or remove their own admin role. Reassign
an account's unfinished active jobs before deactivation or a role change that
would remove technician access. Role changes revoke that account's sessions.

These are implementation protections, **not an independent security audit or a
production-security certification**. Use a limited pilot, review the code, harden
the host, and keep dependencies patched before wider or internet-facing use.

## Backups and recovery

For PostgreSQL/Neon, use `pg_dump` or the provider's export tools and back up R2
separately. The SQLite backup command below deliberately refuses to run when
`DATABASE_URL` is set. Password reset supports either database with the same
environment variables as the server. Render Free has no shell; run maintenance
from a trusted machine with those environment variables.

For local SQLite deployments:

The entire `data/` folder is important: it contains `jobs.sqlite3`, `uploads/`,
and the private setup token. Store it on a persistent disk, not an ephemeral
hosting filesystem.

Stop the server, then run:

```sh
python admin.py backup --server-stopped
```

When using the Windows launcher environment:

```bat
.venv\Scripts\python.exe admin.py backup --server-stopped
```

Backups go to `backups/` by default and include the database and images. Keep them
private and copy them to a separate, protected location. The CSV export is a report,
not a photo/database backup. To restore, stop the server, preserve the current data
folder, and replace it with the extracted backup's `data/` folder. Test recovery
before relying on a backup process. Avoid deleting image files manually.

A server administrator who has lost admin access can run:

```sh
python admin.py reset-password admin@example.com
```

The utility prompts privately for a new temporary password. The account must
change it at next login. There is no email-based reset mechanism.

## Tests

Install test requirements and run:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

PostgreSQL integration checks use isolated schemas in a disposable test database:

```sh
EW_TEST_POSTGRES_URL=postgresql://USER:PASSWORD@TEST_HOST/TEST_DATABASE python -m pytest tests/test_postgres.py -q
```

Never use a production URL for tests. Without this variable, PostgreSQL tests
are skipped. The current validation report is `docs/render-test-results.txt`.

**45 backend tests passed**: the original 28 regression tests and 17 added tests
covering all three roles, requester isolation, privileged-field tampering,
assignment restrictions, notifications, image access, role changes, archived
history, and migration success/rollback. See `docs/TEST_REPORT.md`.

**31 offline Chromium browser assertions passed** at desktop and 390-pixel mobile
widths, including the request -> assignment -> technician completion workflow.
These browser checks used the real FastAPI handlers through a TestClient transport
bridge, plus a localStorage simulator for the preview. They do **not** verify live
browser HTTP/cookie transport or native browser localStorage persistence. Direct
local-server navigation was blocked by this test environment. An optional live
browser check script is included for use in an unrestricted test environment.
No physical iPhone or Android device was used.

## Known boundaries

This is a single-company, small-team starter app. The included preview is not
hosted; the server app has not been deployed to your domain or connected to your
email. SMS, email invitations, mobile push notifications, signatures, GPS,
recurring jobs, multiple assignees, offline synchronization, billing, SSO, MFA,
and formal completion approval are not implemented. In-app notifications require
opening the app. Photo quotas and rate limits are implemented on the server;
there is no automatic retention policy or backup scheduler. The host
administrator must manage backups and provider usage.

SQLite and filesystem uploads are intended for a small deployment with one app
instance on a persistent disk. This release was not load-tested at enterprise
scale. Do not scale it across multiple hosts with separate disks and expect
synchronization. The Render configuration uses shared PostgreSQL and R2; keep
one Free web service for this pilot. Storage and relational data do not share
an atomic transaction, so failed cleanup can require manual reconciliation.

## Project layout

```text
18wheelers-preview.html   Local-only interactive demonstration
start_windows.bat        Windows first-run installer / launcher
start_mac_linux.sh       macOS / Linux launcher
run.py                   Uvicorn application launcher
admin.py                 Backup and account-recovery utilities
app/server.py            FastAPI, authentication and photo endpoints
app/database.py          SQLite/PostgreSQL connections and serialized writes
render.yaml              Render Free service and secret configuration
app/static/              Responsive HTML, CSS and JavaScript
requirements.txt         Versions used for the tested app
requirements-dev.txt     Backend test dependencies
tests/                  45 backend tests, including three-role and migration tests
tools/                   Preview adapter, builder, and optional browser checks
docs/                    Deployment guide, test report, and screenshots
Dockerfile               Optional container build template
```

## Primary implementation references

- FastAPI server deployment: https://fastapi.tiangolo.com/deployment/manually/
- Starlette form uploads: https://www.starlette.io/requests/
- OWASP file-upload guidance:
  https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

These references informed the implementation. They do not certify this application.
