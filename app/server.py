"""18wheelers Jobs: a small-team job and photo workflow with private accounts.

Database uses SQLite in EW_DATA_DIR or PostgreSQL through DATABASE_URL;
photos use local storage or a private R2 bucket.
Run with run.py. All SQL values are parameterized; account and photo authorization
is enforced on the server, independently of the browser interface.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool
from app.photo_storage import PhotoStorage, PhotoMissing, StorageUnavailable
from app.photo_processing import compress_photo
from app.photo_limits import PhotoLimits
from app.database import Database, INTEGRITY_ERRORS, write_lock

ROOT = Path(__file__).resolve().parent
ROLES = ('admin', 'technician', 'requester')
TECHNICIAN_STATUSES = ('In Progress', 'On Hold', 'Completed')
REQUEST_FIELDS = ('title', 'description', 'unit', 'location', 'category', 'priority', 'due_date')
STATUSES = ('New', 'Assigned', 'In Progress', 'On Hold', 'Completed')
PRIORITIES = ('Low', 'Normal', 'High', 'Urgent')
CATEGORIES = ('Maintenance', 'Inspection', 'Delivery', 'Yard', 'Office', 'Other')
MAX_BODY = 32 * 1024 * 1024
MAX_PHOTO = 12 * 1024 * 1024
SESSION_SECONDS = 12 * 60 * 60


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600_000).hex()
    return f'pbkdf2_sha256$600000${salt}${digest}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        kind, iterations, salt, expected = encoded.split('$')
        if kind != 'pbkdf2_sha256':
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def validate_password(value: Any) -> str:
    if not isinstance(value, str) or not 12 <= len(value) <= 128:
        raise HTTPException(400, 'Use a password with 12 to 128 characters.')
    return value


def text(value: Any, field: str, maximum: int, required: bool = False) -> str:
    if value is None:
        value = ''
    if not isinstance(value, str):
        raise HTTPException(400, f'{field} must be text.')
    value = value.strip()
    if (required and not value) or len(value) > maximum:
        raise HTTPException(400, f'{field} is required and must be at most {maximum} characters.' if required else f'{field} must be at most {maximum} characters.')
    return value


def email_value(value: Any) -> str:
    value = text(value, 'Email', 254, True).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise HTTPException(400, 'Enter a valid email address.')
    return value


def choice(value: Any, values: tuple, field: str) -> str:
    if value not in values:
        raise HTTPException(400, f'Invalid {field}.')
    return value


def numeric_id(value: Any, field: str = 'Assignee') -> int | None:
    if value in (None, ''):
        return None
    if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
        raise HTTPException(400, f'Invalid {field}.')
    return int(value)


SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','technician','requester')),
 active INTEGER NOT NULL DEFAULT 1, must_change INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), csrf TEXT NOT NULL,
 expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
 key TEXT PRIMARY KEY, count INTEGER NOT NULL, first_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 unit TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT '', category TEXT NOT NULL,
 priority TEXT NOT NULL, status TEXT NOT NULL, assignee_id INTEGER REFERENCES users(id),
 due_date TEXT NOT NULL DEFAULT '', created_by INTEGER NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT,
 archived INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS photos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL REFERENCES jobs(id),
 filename TEXT NOT NULL UNIQUE, original_name TEXT NOT NULL, phase TEXT NOT NULL,
 caption TEXT NOT NULL DEFAULT '', uploaded_by INTEGER NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL REFERENCES jobs(id),
 user_id INTEGER NOT NULL REFERENCES users(id), kind TEXT NOT NULL, body TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
 job_id INTEGER REFERENCES jobs(id), body TEXT NOT NULL, seen INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_assignee ON jobs(assignee_id);
CREATE INDEX IF NOT EXISTS jobs_creator ON jobs(created_by);
CREATE INDEX IF NOT EXISTS activity_job ON activity(job_id);
CREATE INDEX IF NOT EXISTS photos_job ON photos(job_id);
CREATE INDEX IF NOT EXISTS notifications_user ON notifications(user_id, seen);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires);
'''


def migrate_roles(conn: sqlite3.Connection, store: Path) -> None:
    """Upgrade the original two-role database atomically, without changing IDs.

    Run with the old server stopped. The backup covers the SQLite database;
    a separate full data-folder backup still protects the uploaded photos.
    """
    definition = conn.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0]
    if "'employee'" not in definition:
        conn.execute('PRAGMA user_version=2')
        return
    if conn.in_transaction:
        raise RuntimeError('Role migration must start outside a transaction.')
    backup_path = store / ('jobs-before-three-roles-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + secrets.token_hex(4) + '.sqlite3')
    with sqlite3.connect(backup_path) as backup:
        conn.backup(backup)
    conn.execute('PRAGMA foreign_keys=OFF')
    try:
        conn.execute('BEGIN IMMEDIATE')
        old_sequence = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='users'").fetchone()
        conn.execute("""CREATE TABLE users_three_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','technician','requester')),
            active INTEGER NOT NULL DEFAULT 1, must_change INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        conn.execute("""INSERT INTO users_three_roles
            SELECT id,name,email,password_hash,
                   CASE role WHEN 'employee' THEN 'technician' ELSE role END,
                   active,must_change,created_at FROM users""")
        conn.execute('DROP TABLE users')
        conn.execute('ALTER TABLE users_three_roles RENAME TO users')
        if old_sequence:
            conn.execute("UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name='users'", (old_sequence[0],))
        # A fresh login prevents a browser from retaining a stale role after upgrade.
        conn.execute('DELETE FROM sessions')
        if conn.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Role migration failed a database integrity check; no changes committed.')
        conn.execute('PRAGMA user_version=2')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute('PRAGMA foreign_keys=ON')


class BodyLimitMiddleware:
    """Enforce a cumulative body limit, including chunked multipart uploads."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            length = int(headers.get(b'content-length', b'0'))
        except ValueError:
            return await JSONResponse({'error': 'Invalid content length.'}, 400)(scope, receive, send)
        if length > MAX_BODY:
            return await JSONResponse({'error': 'Upload is too large. Limit: 32 MB per request.'}, 413)(scope, receive, send)
        total = 0
        async def limited_receive():
            nonlocal total
            message = await receive()
            if message['type'] == 'http.request':
                total += len(message.get('body', b''))
                if total > MAX_BODY:
                    raise HTTPException(413, 'Upload is too large. Limit: 32 MB per request.')
            return message
        await self.app(scope, limited_receive, send)


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    store = Path(data_dir or os.environ.get('EW_DATA_DIR', ROOT.parent / 'data')).resolve()
    store.mkdir(parents=True, exist_ok=True)
    uploads = store / 'uploads'
    uploads.mkdir(exist_ok=True)
    photo_storage = PhotoStorage(uploads)
    db_path = store / 'jobs.sqlite3'
    secure_cookie = os.environ.get('EW_SECURE_COOKIES', '0') == '1'
    setup_file = store / '.setup-token'
    db = Database(db_path)
    setup_token = db.initialize(SCHEMA, migrate_roles, store, setup_file)

    photo_limits = PhotoLimits(db, uploads)

    app = FastAPI(title='18wheelers Jobs', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db = db
    app.state.store = store
    app.state.setup_token = setup_token
    app.state.photo_storage = photo_storage
    app.state.photo_limits = photo_limits
    app.add_middleware(BodyLimitMiddleware)

    @app.exception_handler(HTTPException)
    async def api_error(request, exc):
        return JSONResponse({'error': exc.detail}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(StorageUnavailable)
    async def storage_error(request, exc):
        return JSONResponse({'error': 'Photo storage is temporarily unavailable. Please try again.'}, status_code=503)

    @app.exception_handler(PhotoMissing)
    async def missing_photo(request, exc):
        return JSONResponse({'error': str(exc)}, status_code=404)

    @app.middleware('http')
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        image_sources = "'self' blob: data:" + (' ' + photo_storage.image_origin if photo_storage.image_origin else '')
        response.headers['Content-Security-Policy'] = f"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src {image_sources}; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=()'
        if secure_cookie:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if request.url.path.startswith(('/api/', '/photos/')) or request.url.path == '/':
            response.headers['Cache-Control'] = 'no-store'
        return response

    def current_session(request: Request):
        raw = request.cookies.get('ew_session', '')
        if not raw:
            return None
        hashed = hashlib.sha256(raw.encode()).hexdigest()
        with db() as conn:
            row = conn.execute('SELECT * FROM sessions WHERE token_hash=? AND expires>?', (hashed, time.time())).fetchone()
        return row

    def new_session(user_id: int | None, response: Response, old_request: Request):
        raw, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with db() as conn:
            conn.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
            old = current_session(old_request)
            if old:
                conn.execute('DELETE FROM sessions WHERE token_hash=?', (old['token_hash'],))
            conn.execute('INSERT INTO sessions VALUES (?,?,?,?)', (hashlib.sha256(raw.encode()).hexdigest(), user_id, csrf, time.time() + (SESSION_SECONDS if user_id else 1800)))
        response.set_cookie('ew_session', raw, max_age=SESSION_SECONDS if user_id else 1800, httponly=True, secure=secure_cookie, samesite='lax', path='/')
        return csrf

    def check_csrf(request: Request):
        sess = current_session(request)
        csrf = request.headers.get('x-csrf-token', '')
        if not sess or not hmac.compare_digest(csrf, sess['csrf']):
            raise HTTPException(403, 'Your session expired. Refresh the page and try again.')

    def user(request: Request, admin: bool = False, allow_password_change: bool = False):
        sess = current_session(request)
        if not sess or sess['user_id'] is None:
            raise HTTPException(401, 'Please sign in.')
        with db() as conn:
            result = conn.execute('SELECT * FROM users WHERE id=? AND active=1', (sess['user_id'],)).fetchone()
        if not result:
            raise HTTPException(401, 'This account is unavailable. Contact your admin.')
        if result['must_change'] and not allow_password_change:
            raise HTTPException(403, 'Change your temporary password before continuing.')
        if result['role'] not in ROLES:
            raise HTTPException(403, 'This account has an unsupported role.')
        if admin and result['role'] != 'admin':
            raise HTTPException(403, 'Only an admin can do that.')
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            check_csrf(request)
        return result

    def safe_user(row):
        return {key: row[key] for key in ('id', 'name', 'email', 'role', 'active', 'must_change', 'created_at')}

    def job_access(conn, job_id: int, actor):
        row = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        allowed = row and (
            actor['role'] == 'admin'
            or (actor['role'] == 'technician' and row['assignee_id'] == actor['id'])
            or (actor['role'] == 'requester' and row['created_by'] == actor['id'])
        )
        if not allowed:
            raise HTTPException(404, 'Job not found.')
        return row

    def log(conn, job_id, actor_id, kind, body):
        conn.execute('INSERT INTO activity(job_id,user_id,kind,body,created_at) VALUES (?,?,?,?,?)', (job_id, actor_id, kind, body, utcnow()))

    def notify(conn, recipient, job_id, body, actor_id):
        if recipient and recipient != actor_id:
            conn.execute('INSERT INTO notifications(user_id,job_id,body,created_at) VALUES (?,?,?,?)', (recipient, job_id, body, utcnow()))

    def notify_job_participants(conn, job, body, actor_id):
        recipients = {row['id'] for row in conn.execute("SELECT id FROM users WHERE role='admin' AND active=1")}
        recipients.update((job['assignee_id'], job['created_by']))
        for recipient in recipients:
            notify(conn, recipient, job['id'], body, actor_id)

    def check_assignee(conn, assignee_id):
        if assignee_id is not None:
            row = conn.execute("SELECT id FROM users WHERE id=? AND active=1 AND role='technician'", (assignee_id,)).fetchone()
            if not row:
                raise HTTPException(400, 'Choose an active technician.')

    async def payload(request):
        try:
            value = await request.json()
        except (ValueError, UnicodeError):
            raise HTTPException(400, 'Invalid JSON request.')
        if not isinstance(value, dict):
            raise HTTPException(400, 'Expected a JSON object.')
        return value

    def validate_job(data):
        assignee = numeric_id(data.get('assignee_id'))
        status = data.get('status') or ('Assigned' if assignee else 'New')
        due = text(data.get('due_date'), 'Due date', 10)
        if due:
            try:
                if date.fromisoformat(due).isoformat() != due:
                    raise ValueError()
            except ValueError:
                raise HTTPException(400, 'Due date must be YYYY-MM-DD.')
        status = choice(status, STATUSES, 'status')
        if not assignee and status in ('Assigned', 'In Progress'):
            raise HTTPException(400, 'Assign a technician before starting this job.')
        return dict(title=text(data.get('title'), 'Job title', 160, True),
                    description=text(data.get('description'), 'Description', 10000),
                    unit=text(data.get('unit'), 'Truck / unit', 80),
                    location=text(data.get('location'), 'Location', 200),
                    category=choice(data.get('category', 'Maintenance'), CATEGORIES, 'category'),
                    priority=choice(data.get('priority', 'Normal'), PRIORITIES, 'priority'),
                    status=status, assignee_id=assignee, due_date=due)

    def job_dict(conn, row):
        value = dict(row)
        assignee = conn.execute('SELECT name FROM users WHERE id=?', (row['assignee_id'],)).fetchone()
        value['assignee_name'] = assignee['name'] if assignee else ''
        creator = conn.execute('SELECT name FROM users WHERE id=?', (row['created_by'],)).fetchone()
        value['created_by_name'] = creator['name'] if creator else ''
        value['photo_count'] = conn.execute('SELECT COUNT(*) FROM photos WHERE job_id=?', (row['id'],)).fetchone()[0]
        value['comment_count'] = conn.execute("SELECT COUNT(*) FROM activity WHERE job_id=? AND kind='comment'", (row['id'],)).fetchone()[0]
        first = conn.execute('SELECT id FROM photos WHERE job_id=? ORDER BY id LIMIT 1', (row['id'],)).fetchone()
        value['cover_url'] = f'/photos/{first[0]}' if first else None
        return value

    @app.get('/api/session')
    def session_info(request: Request):
        sess = current_session(request)
        with db() as conn:
            setup = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0
            account = conn.execute('SELECT * FROM users WHERE id=? AND active=1', (sess['user_id'],)).fetchone() if sess and sess['user_id'] else None
        response = JSONResponse({})
        csrf = sess['csrf'] if sess else new_session(None, response, request)
        response.body = json.dumps({'needs_setup': setup, 'user': safe_user(account) if account else None, 'csrf': csrf}).encode()
        response.headers['content-length'] = str(len(response.body))
        return response

    @app.post('/api/setup')
    async def setup(request: Request):
        check_csrf(request)
        data = await payload(request)
        token = str(data.get('setup_token', ''))
        if not hmac.compare_digest(token, setup_token):
            raise HTTPException(403, 'Use the setup link shown in the server window.')
        name = text(data.get('name'), 'Name', 100, True)
        email = email_value(data.get('email'))
        encoded = password_hash(validate_password(data.get('password')))
        with db() as conn:
            write_lock(conn)
            if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
                raise HTTPException(409, 'Setup is already complete.')
            cursor = conn.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES (?,?,?,'admin',?) RETURNING id", (name, email, encoded, utcnow()))
            account = conn.execute('SELECT * FROM users WHERE id=?', (cursor.fetchone()[0],)).fetchone()
        response = JSONResponse({})
        csrf = new_session(account['id'], response, request)
        response.body = json.dumps({'user': safe_user(account), 'csrf': csrf}).encode()
        response.headers['content-length'] = str(len(response.body))
        return response

    @app.post('/api/login')
    async def login(request: Request):
        check_csrf(request)
        data = await payload(request)
        email = email_value(data.get('email'))
        password = data.get('password')
        if not isinstance(password, str) or not 1 <= len(password) <= 128:
            raise HTTPException(400, 'Enter your password.')
        ip = request.client.host if request.client else 'unknown'
        keys = ['email:' + email, 'ip:' + ip]
        now = time.time()
        with db() as conn:
            write_lock(conn)
            conn.execute('DELETE FROM attempts WHERE first_at < ?', (now - 900,))
            for key in keys:
                attempt = conn.execute('SELECT * FROM attempts WHERE key=?', (key,)).fetchone()
                limit = 10 if key.startswith('email:') else 60
                if attempt and attempt['count'] >= limit:
                    raise HTTPException(429, 'Too many attempts. Try again in 15 minutes.')
            for key in keys:
                conn.execute('INSERT INTO attempts VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=attempts.count+1', (key, now))
            account = conn.execute('SELECT * FROM users WHERE email=? AND active=1', (email,)).fetchone()
        # Execute the same KDF for unknown accounts to reduce user enumeration.
        valid = verify_password(password, account['password_hash']) if account else verify_password(password, 'pbkdf2_sha256$600000$' + '0'*32 + '$' + '0'*64)
        if not valid:
            raise HTTPException(401, 'Email or password is incorrect.')
        with db() as conn:
            conn.execute('DELETE FROM attempts WHERE key=?', (keys[0],))
        response = JSONResponse({})
        csrf = new_session(account['id'], response, request)
        response.body = json.dumps({'user': safe_user(account), 'csrf': csrf}).encode()
        response.headers['content-length'] = str(len(response.body))
        return response

    @app.post('/api/logout')
    def logout(request: Request):
        check_csrf(request)
        sess = current_session(request)
        with db() as conn:
            conn.execute('DELETE FROM sessions WHERE token_hash=?', (sess['token_hash'],))
        response = JSONResponse({'ok': True})
        response.delete_cookie('ew_session', path='/')
        return response

    @app.post('/api/password')
    async def change_password(request: Request):
        actor = user(request, allow_password_change=True)
        data = await payload(request)
        old = data.get('current_password')
        if not isinstance(old, str) or not 1 <= len(old) <= 128:
            raise HTTPException(400, 'Enter your current password.')
        if not verify_password(old, actor['password_hash']):
            raise HTTPException(400, 'Current password is incorrect.')
        new = validate_password(data.get('new_password'))
        if new == old:
            raise HTTPException(400, 'Choose a different password.')
        with db() as conn:
            conn.execute('UPDATE users SET password_hash=?,must_change=0 WHERE id=?', (password_hash(new), actor['id']))
            conn.execute('DELETE FROM sessions WHERE user_id=?', (actor['id'],))
            account = conn.execute('SELECT * FROM users WHERE id=?', (actor['id'],)).fetchone()
        response = JSONResponse({})
        csrf = new_session(actor['id'], response, request)
        response.body = json.dumps({'user': safe_user(account), 'csrf': csrf}).encode()
        response.headers['content-length'] = str(len(response.body))
        return response

    @app.get('/api/users')
    def list_users(request: Request):
        user(request, admin=True)
        with db() as conn:
            return {'users': [safe_user(row) for row in conn.execute('SELECT * FROM users ORDER BY active DESC,name')]}

    @app.post('/api/users')
    async def add_user(request: Request):
        user(request, admin=True)
        data = await payload(request)
        name, email = text(data.get('name'), 'Name', 100, True), email_value(data.get('email'))
        encoded = password_hash(validate_password(data.get('password')))
        role = choice(data.get('role', 'requester'), ROLES, 'role')
        try:
            with db() as conn:
                cur = conn.execute('INSERT INTO users(name,email,password_hash,role,must_change,created_at) VALUES (?,?,?,?,1,?) RETURNING id', (name,email,encoded,role,utcnow()))
                return {'user': safe_user(conn.execute('SELECT * FROM users WHERE id=?', (cur.fetchone()[0],)).fetchone())}
        except INTEGRITY_ERRORS:
            raise HTTPException(409, 'An account with this email already exists.')

    @app.patch('/api/users/{user_id}')
    async def update_user(user_id: int, request: Request):
        actor = user(request, admin=True)
        data = await payload(request)
        with db() as conn:
            write_lock(conn)
            target = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            if not target:
                raise HTTPException(404, 'Account not found.')
            active = data.get('active', bool(target['active']))
            if not isinstance(active, bool):
                raise HTTPException(400, 'Active must be true or false.')
            role = choice(data.get('role', target['role']), ROLES, 'role')
            if user_id == actor['id'] and (not active or role != 'admin'):
                raise HTTPException(400, 'You cannot deactivate or demote your own admin account.')
            if not active or (role != target['role'] and role != 'technician'):
                open_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE assignee_id=? AND archived=0 AND status!='Completed'", (user_id,)).fetchone()[0]
                if open_count:
                    raise HTTPException(400, 'Reassign this account\'s open jobs before deactivation or changing its role.')
            name = text(data.get('name', target['name']), 'Name', 100, True)
            email = email_value(data.get('email', target['email']))
            try:
                conn.execute('UPDATE users SET name=?,email=?,role=?,active=? WHERE id=?', (name,email,role,int(active),user_id))
            except INTEGRITY_ERRORS:
                raise HTTPException(409, 'Email address already in use.')
            if 'password' in data:
                conn.execute('UPDATE users SET password_hash=?,must_change=1 WHERE id=?', (password_hash(validate_password(data['password'])),user_id))
            if not active or 'password' in data or role != target['role']:
                conn.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
            return {'user': safe_user(conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone())}

    @app.get('/api/jobs')
    def list_jobs(request: Request):
        actor = user(request)
        archived = request.query_params.get('archived') == '1'
        with db() as conn:
            if actor['role'] == 'admin':
                rows = conn.execute('SELECT * FROM jobs WHERE archived=? ORDER BY updated_at DESC,id DESC', (int(archived),)).fetchall()
            elif actor['role'] == 'technician':
                rows = conn.execute('SELECT * FROM jobs WHERE archived=? AND assignee_id=? ORDER BY updated_at DESC,id DESC', (int(archived),actor['id'])).fetchall()
            else:
                rows = conn.execute('SELECT * FROM jobs WHERE archived=? AND created_by=? ORDER BY updated_at DESC,id DESC', (int(archived),actor['id'])).fetchall()
            return {'jobs': [job_dict(conn,row) for row in rows]}

    @app.post('/api/jobs')
    async def create_job(request: Request):
        actor = user(request)
        if actor['role'] not in ('admin', 'requester'):
            raise HTTPException(403, 'Only admins and requesters can create jobs.')
        incoming = await payload(request)
        if actor['role'] == 'requester':
            if set(incoming) - set(REQUEST_FIELDS):
                raise HTTPException(403, 'Requesters can submit requests, but cannot assign work or set job status.')
            incoming = {**incoming, 'status': 'New', 'assignee_id': None}
        data = validate_job(incoming)
        now = utcnow()
        with db() as conn:
            check_assignee(conn, data['assignee_id'])
            fields = list(data)
            cur = conn.execute('INSERT INTO jobs(' + ','.join(fields) + ',created_by,created_at,updated_at,completed_at) VALUES (' + ','.join(['?']*(len(fields)+4)) + ') RETURNING id', [data[f] for f in fields] + [actor['id'],now,now,now if data['status']=='Completed' else None])
            job_id = cur.fetchone()[0]
            log(conn, job_id, actor['id'], 'created', 'Submitted this request.' if actor['role']=='requester' else 'Created this job.')
            if actor['role'] == 'requester':
                for admin in conn.execute("SELECT id FROM users WHERE role='admin' AND active=1"):
                    notify(conn, admin['id'], job_id, f'New request from {actor["name"]}: {data["title"]}', actor['id'])
            notify(conn, data['assignee_id'],job_id, f'Assigned to you: {data["title"]}',actor['id'])
            return {'job': job_dict(conn, conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())}

    @app.get('/api/jobs/{job_id}')
    def get_job(job_id: int, request: Request):
        actor = user(request)
        with db() as conn:
            job = job_dict(conn, job_access(conn,job_id,actor))
            photos = [dict(row) for row in conn.execute('SELECT p.id,p.original_name,p.phase,p.caption,p.created_at,u.name AS uploaded_by_name FROM photos p JOIN users u ON u.id=p.uploaded_by WHERE p.job_id=? ORDER BY p.id DESC', (job_id,))]
            for photo in photos:
                photo['url'] = f'/photos/{photo["id"]}'
            activity = [dict(row) for row in conn.execute('SELECT a.id,a.kind,a.body,a.created_at,u.name AS user_name FROM activity a JOIN users u ON u.id=a.user_id WHERE a.job_id=? ORDER BY a.id DESC', (job_id,))]
            return {'job': job, 'photos': photos, 'activity': activity}

    @app.patch('/api/jobs/{job_id}')
    async def update_job(job_id: int, request: Request):
        actor = user(request)
        incoming = await payload(request)
        if actor['role'] == 'requester':
            raise HTTPException(403, 'Requesters can add photos and comments, but cannot change job details or status.')
        if actor['role'] == 'technician':
            if set(incoming) - {'status','version'}:
                raise HTTPException(403, 'Only admins can edit job details and assignments.')
            if 'status' in incoming and incoming['status'] not in TECHNICIAN_STATUSES:
                raise HTTPException(403, 'Technicians can select In Progress, On Hold, or Completed.')
        with db() as conn:
            write_lock(conn)
            old = job_access(conn,job_id,actor)
            if old['archived']:
                raise HTTPException(400, 'Restore this job before editing it.')
            if incoming.get('version') != old['version']:
                raise HTTPException(409, 'This job changed in another session. Close and reopen it before saving.')
            fields = ('title','description','unit','location','category','priority','status','assignee_id','due_date')
            merged = {field: incoming.get(field,old[field]) for field in fields}
            values = validate_job(merged)
            if values['assignee_id'] != old['assignee_id']:
                check_assignee(conn,values['assignee_id'])
            completed = old['completed_at']
            if values['status'] != old['status']:
                completed = utcnow() if values['status']=='Completed' else None
                log(conn,job_id,actor['id'],'status',f'Status changed: {old["status"]} -> {values["status"]}.')
                recipients = [row['id'] for row in conn.execute("SELECT id FROM users WHERE role='admin' AND active=1")]
                recipients.extend((values['assignee_id'], old['created_by']))
                for recipient in set(recipients):
                    notify(conn,recipient,job_id,f'{values["title"]}: {values["status"]}',actor['id'])
            if values['assignee_id'] != old['assignee_id']:
                person = conn.execute('SELECT name FROM users WHERE id=?',(values['assignee_id'],)).fetchone()
                log(conn,job_id,actor['id'],'assignment',f'Assigned to {person["name"] if person else "no one"}.')
                notify(conn,values['assignee_id'],job_id,f'Assigned to you: {values["title"]}',actor['id'])
                notify(conn,old['created_by'],job_id,f'{values["title"]}: assigned to {person["name"] if person else "no one"}',actor['id'])
            changed = [field for field in fields if values[field] != old[field] and field not in ('status','assignee_id')]
            if changed:
                log(conn,job_id,actor['id'],'edited','Updated: ' + ', '.join(field.replace('_',' ') for field in changed) + '.')
            conn.execute('UPDATE jobs SET '+','.join(field+'=?' for field in fields)+',updated_at=?,completed_at=?,version=version+1 WHERE id=?', [values[f] for f in fields]+[utcnow(),completed,job_id])
            return {'job':job_dict(conn,conn.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone())}

    @app.post('/api/jobs/{job_id}/archive')
    async def archive_job(job_id: int, request: Request):
        actor = user(request,admin=True)
        data = await payload(request)
        archived = data.get('archived',True)
        if not isinstance(archived,bool):
            raise HTTPException(400,'Archived must be true or false.')
        with db() as conn:
            write_lock(conn)
            job_access(conn,job_id,actor)
            conn.execute('UPDATE jobs SET archived=?,updated_at=?,version=version+1 WHERE id=?',(int(archived),utcnow(),job_id))
            log(conn,job_id,actor['id'],'archived','Archived this job.' if archived else 'Restored this job.')
        return {'ok':True}

    @app.post('/api/jobs/{job_id}/comments')
    async def add_comment(job_id: int, request: Request):
        actor = user(request)
        data = await payload(request)
        body = text(data.get('body'),'Comment',5000,True)
        with db() as conn:
            job = job_access(conn,job_id,actor)
            if job['archived']:
                raise HTTPException(400,'Restore this job before adding comments.')
            log(conn,job_id,actor['id'],'comment',body)
            notify_job_participants(conn,job,f'{actor["name"]} commented on {job["title"]}',actor['id'])
        return {'ok':True}

    @app.get('/api/storage/usage')
    def storage_usage(request: Request):
        user(request, admin=True)
        return {**photo_limits.usage(), 'backend': photo_storage.backend}

    @app.post('/api/jobs/{job_id}/photos')
    async def add_photos(job_id: int, request: Request):
        actor = user(request)
        with db() as conn:
            job = job_access(conn,job_id,actor)
            if job['archived']:
                raise HTTPException(400,'Restore this job before adding photos.')
        photo_limits.upload_attempt(actor['id'])
        with photo_limits.processing():
            processed = []
            async with request.form(max_files=8,max_fields=4,max_part_size=10000) as form:
                phase = choice(str(form.get('phase','Before')),('Before','After','General'),'photo type')
                if actor['role'] == 'requester' and phase == 'After':
                    raise HTTPException(403, 'Requesters can add Before or General photos; After photos document technician work.')
                caption = text(form.get('caption'),'Caption',500)
                files = form.getlist('files')
                if not files or len(files)>8 or any(not isinstance(f,UploadFile) for f in files):
                    raise HTTPException(400,'Choose 1 to 8 image files.')
                photo_limits.upload_photos(actor['id'], len(files))
                for item in files:
                    raw = await item.read(MAX_PHOTO+1)
                    if len(raw)>MAX_PHOTO:
                        raise HTTPException(400,'Each photo must be 12 MB or smaller.')
                    content = await run_in_threadpool(compress_photo, raw, photo_limits.max_stored,
                                                     photo_limits.max_dimension, photo_limits.quality)
                    processed.append((secrets.token_hex(24)+'.webp',
                                      text(item.filename,'Filename',255) or 'photo.webp',content))
            reservation = photo_limits.reserve(job_id, [len(content) for _,_,content in processed])
            written = []
            try:
                for filename,original,content in processed:
                    reference = await run_in_threadpool(photo_storage.put, filename, content)
                    written.append(reference)
                with db() as conn:
                    write_lock(conn)
                    fresh = job_access(conn,job_id,actor)
                    if fresh['archived']:
                        raise HTTPException(400,'This job has been archived.')
                    for reference,(_,original,content) in zip(written,processed):
                        conn.execute('INSERT INTO photos(job_id,filename,original_name,phase,caption,uploaded_by,created_at,stored_bytes) VALUES (?,?,?,?,?,?,?,?)',
                                     (job_id,reference,original,phase,caption,actor['id'],utcnow(),len(content)))
                    log(conn,job_id,actor['id'],'photos',f'Added {len(processed)} {phase.lower()} photo(s).')
                    notify_job_participants(conn,fresh,f'{actor["name"]} added photos to {fresh["title"]}',actor['id'])
                    conn.execute('DELETE FROM photo_reservations WHERE token=?', (reservation,))
            except Exception as exc:
                cleaned = not (isinstance(exc, StorageUnavailable) and exc.cleanup_failed)
                for reference in written:
                    removed = await run_in_threadpool(photo_storage.cleanup, reference)
                    cleaned = cleaned and removed
                # Keep the reservation if cleanup failed. Never undercount possible orphan objects.
                if cleaned:
                    photo_limits.release(reservation)
                raise
            return {'ok':True,'count':len(processed)}

    @app.get('/photos/{photo_id}')
    def photo(photo_id: int, request: Request):
        actor=user(request)
        with db() as conn:
            record=conn.execute('SELECT * FROM photos WHERE id=?',(photo_id,)).fetchone()
            if not record:
                raise HTTPException(404,'Photo not found.')
            job_access(conn,record['job_id'],actor)
        photo_limits.read_attempt(actor['id'])
        return photo_storage.response(record['filename'])

    @app.delete('/api/photos/{photo_id}')
    def delete_photo(photo_id: int, request: Request):
        actor=user(request,admin=True)
        with db() as conn:
            write_lock(conn)
            record=conn.execute('SELECT * FROM photos WHERE id=?',(photo_id,)).fetchone()
            if not record:
                raise HTTPException(404,'Photo not found.')
            job=job_access(conn,record['job_id'],actor)
            if job['archived']:
                raise HTTPException(400,'Restore this job before deleting photos.')
            # Keep the row if R2 rejects deletion, so the administrator can retry.
            photo_storage.delete(record['filename'])
            conn.execute('DELETE FROM photos WHERE id=?',(photo_id,))
            log(conn,record['job_id'],actor['id'],'photos','Removed a photo.')
        return {'ok':True}

    @app.get('/api/notifications')
    def notifications(request: Request):
        actor=user(request)
        with db() as conn:
            rows=conn.execute('''SELECT n.* FROM notifications n JOIN jobs j ON j.id=n.job_id
                WHERE n.user_id=? AND (?='admin' OR (?='technician' AND j.assignee_id=?)
                OR (?='requester' AND j.created_by=?)) ORDER BY n.id DESC LIMIT 50''',
                (actor['id'],actor['role'],actor['role'],actor['id'],actor['role'],actor['id'])).fetchall()
            return {'notifications':[dict(row) for row in rows]}

    @app.post('/api/notifications/read')
    def read_notifications(request: Request):
        actor=user(request)
        with db() as conn:
            conn.execute('UPDATE notifications SET seen=1 WHERE user_id=?',(actor['id'],))
        return {'ok':True}

    @app.get('/api/export')
    def export(request: Request):
        actor=user(request,admin=True)
        columns=['id','title','unit','category','status','priority','assignee_name','created_by_name','due_date','location','description','photo_count','created_at','completed_at','archived']
        output=io.StringIO(newline='')
        writer=csv.writer(output)
        writer.writerow(columns)
        def safe_cell(value):
            if value is None:return ''
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r','\n')):
                return "'"+value
            return value
        with db() as conn:
            for row in conn.execute('SELECT * FROM jobs ORDER BY id'):
                item=job_dict(conn,row)
                writer.writerow([safe_cell(item.get(c)) for c in columns])
        return Response('\ufeff'+output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="18wheelers-jobs.csv"'})

    @app.get('/health')
    def health():
        return {'status':'ok'}

    @app.get('/')
    def index():
        return FileResponse(ROOT/'static'/'index.html',media_type='text/html')

    app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
    return app
