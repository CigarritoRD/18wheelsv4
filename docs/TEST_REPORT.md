# Three-role test report

Updated October 5, 2026. All test data and identities are fictional. No company
records, employee roster, real passwords, or production database were used.

## Backend: 45 passing tests

Command: `python -m pytest -q`.

The original 28 tests cover authentication, temporary-password changes, CSRF,
session rotation/revocation, permission boundaries, private photos, image decoding
and metadata removal, size limits, archive/restore, comments, notifications,
concurrent edits, CSV formula protection, persistence, and security headers.
They were retained with the original Employee role renamed to Technician.

Seventeen new tests cover Requester submissions, strict ownership, privileged-field
rejection, blocked account/export/archive/status actions, active-technician-only
assignment, the complete requester-to-technician workflow, photo-phase permissions,
technician status choices, scoped read-only history, the Requester default role,
reassignment, role changes/session revocation, notification isolation, idempotent
legacy migration, preserved data/photos, a pre-migration database backup, and
transaction rollback when foreign-key integrity checks fail. The additional backup
regression verifies that the backup utility does not initialize or migrate the
original database before making a copy.

The migration test uses a synthetic database matching the original schema. It does
not prove recovery for every modified, corrupted, or very large customer database.
A verified full data backup and a limited pilot remain necessary.

## Browser UI: 31 passing offline assertions

Command: `python tools/browser_check_offline.py`.
Chromium 144.0.7559.96 with Playwright 1.57.0; desktop 1440 x 1000 and mobile-width
390 x 844 layouts. The checks exercise both the full-app interface and the standalone
preview. The full-app UI sends real handler requests through a FastAPI TestClient
bridge, including per-account server sessions, CSRF headers, and file uploads.
Photo responses are bridged as data URLs for rendering. Preview persistence uses a
localStorage simulator. Screenshots are in this folder.

The UI checks include creation of Technician and Requester accounts, default role,
role menus, limited screens, ownership filtering, new request/photo submission,
admin assignment, technician status updates, after photos, comments, requester
completion visibility, three preview role views, and horizontal-fit mobile checks.
No JavaScript runtime errors were observed in those checked flows.

**Limitations:** Direct navigation to the localhost test server was blocked by the
managed browser in this environment. Consequently these are not live HTTP/browser
cookie tests, not native localStorage durability tests, and not a deployment test.
The optional `tools/browser_check_three_roles.py` performs a normal local-server
check in an environment that permits it; it was not completed here. No Safari,
Firefox, Edge, physical iPhone/Android, screen-reader, adversarial penetration,
load, or production-network testing was performed in this update.

## Reproduce

For backend tests, install `requirements-dev.txt` and run pytest. The tested versions
of the runtime dependencies remain in `requirements.txt`; no dependency update was
part of this role change. Browser checks additionally require Playwright and an
installed Chromium browser. Install its browser using Playwright's normal installer
or set `EW_BROWSER_PATH` to your permitted browser executable. The browser scripts
are optional and do not ship or create production login accounts.

These results are engineering checks, not an independent security audit or a
production-readiness certification. Review, deploy with HTTPS, manage permissions,
back up persistent storage, and pilot on the actual devices before relying on it.
