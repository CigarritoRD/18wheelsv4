"""Database backends for local SQLite and hosted Supabase Postgres."""
from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path


try:  # Optional during a local-only install; required when DATABASE_URL is set.
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - exercised only in intentionally minimal installs.
    psycopg = None
    dict_row = None
    ConnectionPool = None


if psycopg:
    INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)
else:
    INTEGRITY_ERRORS = (sqlite3.IntegrityError,)


def connection_failure(error) -> str:
    """Emit only fixed diagnostics: driver messages can contain credentials."""
    detail = str(error).lower()
    state = getattr(error, 'sqlstate', None)
    signatures = (
        ('DB_AUTH', ('password authentication failed',), 'The database rejected the credentials.'),
        ('DB_URL', ('invalid sslmode value', 'invalid connection option', 'invalid uri', 'invalid percent-encoded'), 'The database URL contains an invalid option or encoding.'),
        ('DB_TLS_CERT', ('certificate verify failed', 'certificate has expired', 'self-signed certificate', 'does not match host name'), 'TLS certificate verification failed.'),
        ('DB_TLS_INTERNAL', ('alert internal error',), 'The database endpoint sent a TLS internal-error alert.'),
        ('DB_TLS_RECORD', ('bad record mac', 'decryption failed'), 'TLS record verification failed.'),
        ('DB_CONNECTION_CLOSED', ('ssl connection has been closed unexpectedly', 'eof detected', 'connection reset', 'unexpected eof', 'closed the connection'), 'The endpoint closed the connection during startup.'),
        ('DB_TLS_PROTOCOL', ('wrong version number', 'unsupported protocol', 'handshake failure'), 'TLS negotiation failed.'),
        ('DB_DNS', ('could not translate host name', 'name or service not known', 'name resolution'), 'The database hostname could not be resolved.'),
        ('DB_DATABASE', ('does not exist',), 'The requested database or role does not exist.'),
        ('DB_TIMEOUT', ('timeout', 'timed out'), 'The database connection timed out.'),
        ('DB_NETWORK', ('connection refused', 'network is unreachable', 'no route to host'), 'The database endpoint could not be reached.'),
        ('DB_ACCESS', ('tenant or user not found', 'no pg_hba'), 'The database rejected the project or user.'),
    )
    for code, fragments, explanation in signatures:
        if any(fragment in detail for fragment in fragments):
            return code + ': ' + explanation + ' Keep SSL enabled; check Supabase Connect.'
    suffix = ' SQLSTATE=' + state if isinstance(state, str) and re.fullmatch(r'[A-Z0-9]{5}', state) else ''
    return 'DB_CONNECT: Database connection failed; no raw driver message is logged.' + suffix


if psycopg:
    class SafePostgresConnection(psycopg.Connection):
        @classmethod
        def connect(cls, *args, **kwargs):
            try:
                return super().connect(*args, **kwargs)
            except psycopg.Error as error:
                # Pool reconnect warnings must never log arbitrary server text.
                raise psycopg.OperationalError(connection_failure(error)) from None


class PostgresCursor:
    """Small compatibility layer for the sqlite Row/Cursor API used by the app."""

    def __init__(self, cursor=None):
        self.cursor = cursor

    @staticmethod
    def _row(row):
        return FlexibleRow(row) if row is not None else None

    def fetchone(self):
        return self._row(self.cursor.fetchone()) if self.cursor else None

    def fetchall(self):
        return [self._row(row) for row in self.cursor.fetchall()] if self.cursor else []

    def __iter__(self):
        if not self.cursor:
            return iter(())
        return (self._row(row) for row in self.cursor)


class FlexibleRow(dict):
    """Mapping row that also accepts numeric indexes like sqlite3.Row."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        if isinstance(key, slice):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def _sql(statement: str) -> str:
        tokens = re.split(r"('(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")", statement)
        return ''.join(part.replace('%', '%%') if index % 2 else
                       part.replace('%', '%%').replace('?', '%s')
                       for index, part in enumerate(tokens))

    def execute(self, statement: str, parameters=None):
        if statement.strip().upper() == 'BEGIN IMMEDIATE':
            # The pool context already owns a Postgres transaction. SQLite needs
            # this explicit lock; Postgres row updates provide the concurrency.
            return PostgresCursor()
        cursor = (self.connection.execute(statement) if parameters is None else
                  self.connection.execute(self._sql(statement), parameters))
        return PostgresCursor(cursor)


class Database:
    """Select SQLite for local use or Supabase Postgres via DATABASE_URL."""

    def __init__(self, sqlite_path: Path, database_url: str | None = None):
        self.sqlite_path = sqlite_path
        self.database_url = database_url
        self.backend = 'postgres' if database_url else 'sqlite'
        self.pool = None
        if os.environ.get('RENDER') == 'true' and not database_url:
            raise RuntimeError('Render requires DATABASE_URL; SQLite on the local disk is not persistent.')
        if self.backend == 'postgres':
            if not psycopg or not ConnectionPool:
                raise RuntimeError(
                    'DATABASE_URL is set, but Postgres dependencies are missing. '
                    'Install requirements.txt before starting the app.'
                )
            pool_size = int(os.environ.get('EW_DB_POOL_SIZE', '5'))
            if not 1 <= pool_size <= 20:
                raise RuntimeError('EW_DB_POOL_SIZE must be between 1 and 20.')
            self.pool = ConnectionPool(
                conninfo=database_url,
                min_size=1,
                max_size=pool_size,
                connection_class=SafePostgresConnection,
                kwargs={'row_factory': dict_row, 'prepare_threshold': None, 'connect_timeout': 10},
                open=False,
            )
            self.pool.open()
            try:
                self.pool.wait(timeout=15)
            except Exception:
                self.pool.close()
                raise RuntimeError('DB_STARTUP: The Postgres pool could not start. See the safe DB_* diagnostics above.') from None

    @contextmanager
    def connection(self):
        if self.backend == 'sqlite':
            conn = sqlite3.connect(self.sqlite_path, timeout=20)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA busy_timeout=20000')
            try:
                with conn:
                    yield conn
            finally:
                conn.close()
            return

        with self.pool.connection() as raw:
            # The schema is deliberately outside Supabase's exposed `public`
            # schema. Keep this transaction-scoped so pooled connections cannot
            # leak session state between applications.
            raw.execute('SET LOCAL search_path TO app_private, pg_catalog')
            yield PostgresConnection(raw)

    def check_postgres_schema(self):
        if self.backend != 'postgres':
            return
        with self.pool.connection() as raw:
            row = raw.execute("SELECT to_regclass('app_private.users') AS table_name").fetchone()
            if not row or not row['table_name']:
                raise RuntimeError(
                    'Supabase is reachable, but the app schema is missing. '
                    'Apply the files in supabase/migrations before starting the server.'
                )

    def close(self):
        if self.pool:
            self.pool.close()
