# Upgrade to Admin / Technician / Requester

This is a new application package, not a change to a running hosted website.
Do not run the old and new servers against the same data folder at the same time.

## Before changing anything

1. Stop the old server (Ctrl+C in its server window).
2. Back up its entire `data/` folder, including `jobs.sqlite3`, `uploads/`, and
   `.setup-token`. Keep the backup outside the application folder. The existing
   `python admin.py backup --server-stopped` utility is also available.
3. Keep the original application folder unchanged as a rollback copy.
4. Extract the new ZIP into a **different** folder. Do not copy the old `.venv`.
5. Copy the backed-up `data/` folder into the new application's root, alongside
   `run.py`. An installation using `EW_DATA_DIR` must instead point that variable
   at a protected copy of the intended data folder. Verify the path before launch.

## First launch

Start `start_windows.bat` (Windows) or `sh start_mac_linux.sh` (macOS/Linux).
The new server automatically detects the original two-role user table and:

- Creates `data/jobs-before-three-roles-<timestamp>-<random>.sqlite3`, a database-only
  pre-migration backup. This is **not** a substitute for the full backup with photos.
- Rebuilds the user table in a transaction, changing `employee` to `technician`.
- Keeps `admin` accounts as Admin, retaining IDs, passwords, account activation,
  password-change requirements, jobs, assignments, photos, activity, and notifications.
- Checks foreign-key integrity before committing, then clears existing sessions.

Everyone must sign in again. Existing passwords are unchanged. The migration is
idempotent: a migrated database is not migrated again on ordinary restarts.
If integrity validation fails, the migration rolls back and startup stops. Do not
remove database records to force it through; restore a verified backup or investigate
the reported problem. Tests cover successful migration, restart, and rollback.

## Review account roles and assignments

In **Team**, Admins can create or edit accounts with exactly these roles:

**Admin:** all job visibility, assignments, account controls, exports, and history.
**Technician:** only currently assigned work; progress, photos, and comments.
**Requester:** submit requests and see only their own submitted requests.

New accounts default to Requester. Existing Employee accounts become Technicians;
no account is automatically identified as a requester. Change a person's role only
after checking the access they need. Reassign unfinished active jobs before changing
a Technician to Requester/Admin or deactivating their account. Role changes sign out
that account's existing sessions. A current admin cannot demote/deactivate themselves.

Legacy jobs assigned to an Admin keep that historical assignment during migration;
review and reassign unfinished ones to a Technician. New assignments must target an
active Technician. The requester is the job's original `created_by` user; existing
manager-created jobs are not automatically re-attributed to a driver or requester.
Changing a role does not transfer ownership of existing requests. Account permissions
apply immediately after the person's new login.

## Pilot check before giving the team access

Use disposable pilot accounts to submit a Requester job, assign it as Admin, update
it as Technician, add before/after photos, and confirm the Requester sees completion.
Verify a second requester cannot open it and an unassigned technician cannot see it.
Check login, logout, password changes, uploads, and backup recovery in your actual
browser/server setup. The included automated browser checks were offline transport
checks; production browser-cookie behavior still needs this pilot.

## Rollback

Stop the new server. Restore the **full pre-upgrade data backup** into a separate
copy of the original application and run the original version there. Do not run the
old application directly against a migrated database. Any work entered after the
backup will need reconciliation before rollback; it is not merged automatically.

## Shared access

This ZIP does not deploy the app to the internet. Follow `DEPLOYMENT.md` for a
reviewed single-instance server with persistent storage, HTTPS, and backups.
Do not expose a development/local server casually or share a setup token.
