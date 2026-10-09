"""Persistent upload quotas, serialized across workers on either database."""
from contextlib import contextmanager
import os
import secrets
import threading
import time
from fastapi import HTTPException
from app.database import write_lock, photo_columns


def setting(name, default, low, high):
    value = int(os.environ.get(name, str(default)))
    if not low <= value <= high:
        raise ValueError(f'{name} must be between {low} and {high}.')
    return value


class PhotoLimits:
    def __init__(self, db, uploads):
        self.db = db
        self.total_limit = setting('EW_PHOTO_TOTAL_LIMIT_MB', 5000, 1, 8000) * 1024 * 1024
        self.max_stored = setting('EW_PHOTO_MAX_STORED_KB', 300, 32, 1024) * 1024
        self.max_dimension = setting('EW_PHOTO_MAX_DIMENSION', 1600, 800, 2400)
        self.quality = setting('EW_PHOTO_WEBP_QUALITY', 80, 60, 90)
        self.per_job = setting('EW_PHOTO_MAX_PER_JOB', 100, 1, 1000)
        self.user_minute = setting('EW_UPLOAD_REQUESTS_USER_MINUTE', 3, 1, 10)
        self.global_minute = setting('EW_UPLOAD_REQUESTS_GLOBAL_MINUTE', 20, 1, 60)
        self.user_daily = setting('EW_UPLOAD_PHOTOS_USER_DAY', 100, 1, 500)
        self.global_daily = setting('EW_UPLOAD_PHOTOS_GLOBAL_DAY', 500, 1, 2000)
        self.upload_month = setting('EW_UPLOAD_REQUESTS_GLOBAL_MONTH', 50000, 1, 100000)
        self.read_user_minute = setting('EW_PHOTO_READS_USER_MINUTE', 120, 1, 300)
        self.read_month = setting('EW_PHOTO_READS_GLOBAL_MONTH', 500000, 1, 1000000)
        self.processing_slots = threading.BoundedSemaphore(2)
        with db() as conn:
            write_lock(conn)
            columns = photo_columns(conn)
            if 'stored_bytes' not in columns:
                if db.schema:
                    raise RuntimeError('Apply the Supabase photo quota migration before starting the server.')
                conn.execute('ALTER TABLE photos ADD COLUMN stored_bytes BIGINT NOT NULL DEFAULT 0')
            if not db.schema:
                conn.execute('''CREATE TABLE IF NOT EXISTS photo_reservations (
                    token TEXT PRIMARY KEY, job_id INTEGER NOT NULL, bytes_count BIGINT NOT NULL,
                    photo_count INTEGER NOT NULL, created_at DOUBLE PRECISION NOT NULL)''')
                conn.execute('''CREATE TABLE IF NOT EXISTS photo_counters (
                    key TEXT PRIMARY KEY, used INTEGER NOT NULL, expires DOUBLE PRECISION NOT NULL)''')
            # Account for legacy local images. Unknown remote sizes block new uploads.
            for row in conn.execute('SELECT id,filename FROM photos WHERE stored_bytes=0'):
                if not row['filename'].startswith('r2:'):
                    path = uploads / row['filename']
                    if path.parent == uploads and path.is_file():
                        conn.execute('UPDATE photos SET stored_bytes=? WHERE id=?', (path.stat().st_size, row['id']))

    def take(self, counters):
        now = time.time()
        with self.db() as conn:
            write_lock(conn)
            conn.execute('DELETE FROM photo_counters WHERE expires<=?', (now,))
            pending = []
            for name, amount, limit, period in counters:
                # Fixed UTC windows; month counters use 30-day windows.
                start = int(now // period) * period
                key = f'{name}:{start}'
                row = conn.execute('SELECT used FROM photo_counters WHERE key=?', (key,)).fetchone()
                used = row['used'] if row else 0
                if used + amount > limit:
                    raise HTTPException(429, 'Photo request limit reached. Please try later.',
                                        headers={'Retry-After': str(max(1, int(start + period - now)))})
                pending.append((key, used + amount, start + period))
            conn.executemany('INSERT INTO photo_counters VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET used=excluded.used,expires=excluded.expires', pending)

    def upload_attempt(self, user_id):
        self.take([(f'upload-user-{user_id}', 1, self.user_minute, 60),
                   ('upload-global', 1, self.global_minute, 60),
                   ('upload-month', 1, self.upload_month, 30*86400)])

    def upload_photos(self, user_id, count):
        # Attempts consume daily quota, including failures, to bound retries.
        self.take([(f'upload-day-user-{user_id}', count, self.user_daily, 86400),
                   ('upload-day-global', count, self.global_daily, 86400)])

    def read_attempt(self, user_id):
        self.take([(f'read-user-{user_id}', 1, self.read_user_minute, 60),
                   ('read-month', 1, self.read_month, 30*86400)])

    @contextmanager
    def processing(self):
        if not self.processing_slots.acquire(blocking=False):
            raise HTTPException(429, 'Two photo uploads are already being processed. Please retry shortly.',
                                headers={'Retry-After': '5'})
        try:
            yield
        finally:
            self.processing_slots.release()

    def reserve(self, job_id, sizes):
        token = secrets.token_hex(24)
        with self.db() as conn:
            write_lock(conn)
            if conn.execute('SELECT 1 FROM photos WHERE stored_bytes=0 LIMIT 1').fetchone():
                raise HTTPException(409, 'Photo sizes need reconciliation before more uploads. Contact your administrator.')
            stored = conn.execute('SELECT COALESCE(SUM(stored_bytes),0) FROM photos').fetchone()[0]
            pending = conn.execute('SELECT COALESCE(SUM(bytes_count),0) FROM photo_reservations').fetchone()[0]
            if stored + pending + sum(sizes) > self.total_limit:
                raise HTTPException(413, 'Photo storage limit reached. Ask an administrator to free space.')
            count = conn.execute('SELECT COUNT(*) FROM photos WHERE job_id=?', (job_id,)).fetchone()[0]
            reserved = conn.execute('SELECT COALESCE(SUM(photo_count),0) FROM photo_reservations WHERE job_id=?', (job_id,)).fetchone()[0]
            if count + reserved + len(sizes) > self.per_job:
                raise HTTPException(413, 'This job has reached its photo limit.')
            conn.execute('INSERT INTO photo_reservations VALUES (?,?,?,?,?)', (token, job_id, sum(sizes), len(sizes), time.time()))
        return token

    def release(self, token):
        with self.db() as conn:
            conn.execute('DELETE FROM photo_reservations WHERE token=?', (token,))

    def usage(self):
        with self.db() as conn:
            used = conn.execute('SELECT COALESCE(SUM(stored_bytes),0) FROM photos').fetchone()[0]
            pending = conn.execute('SELECT COALESCE(SUM(bytes_count),0) FROM photo_reservations').fetchone()[0]
            unknown = conn.execute('SELECT COUNT(*) FROM photos WHERE stored_bytes=0').fetchone()[0]
        return {'stored_bytes': int(used), 'reserved_bytes': int(pending), 'limit_bytes': self.total_limit,
                'unknown_photo_sizes': unknown, 'max_photo_bytes': self.max_stored,
                'max_per_job': self.per_job, 'format': 'webp'}
