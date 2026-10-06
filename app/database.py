"""Small database boundary: SQLite locally, PostgreSQL when DATABASE_URL is set.

Only application-authored SQL crosses this boundary. Values always remain bound
parameters. PostgreSQL transactions use transaction-scoped advisory locks for
the operations that require the same serialization as SQLite BEGIN IMMEDIATE.
"""
from contextlib import contextmanager
import os
import re
import sqlite3

import psycopg

INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)
WRITE_LOCK = 187336201


def connection_failure(error):
    """Classify driver failures; never copy driver text/credentials to logs.

    libpq connection errors often have no SQLSTATE, so fixed message fragments
    are a fallback. All emitted text is application-owned, even if the server
    sends an error containing a URL, password or arbitrary remote text.
    """
    state = getattr(error, 'sqlstate', None)
    detail = str(error).lower()
    if state == '28P01' or 'password authentication failed' in detail:
        return 'DB_AUTH: PostgreSQL rejected the username/password. Copy a fresh Neon connection URL with the actual password into DATABASE_URL.'
    if 'channel binding' in detail:
        return 'DB_CHANNEL_BINDING: The connection failed its channel-binding requirement. Check the SSL parameters in the Neon connection URL.'
    if any(part in detail for part in ('could not translate host name', 'name or service not known', 'name resolution', 'nodename nor servname')):
        return 'DB_DNS: The database hostname could not be resolved. Check that DATABASE_URL contains the exact Neon hostname.'
    if state == '3D000' or ('database' in detail and 'does not exist' in detail):
        return 'DB_DATABASE: The requested database does not exist. Copy the URL for the correct database from Neon Connect.'
    if state == '53300' or any(part in detail for part in ('too many connections', 'too many clients', 'remaining connection slots')):
        return 'DB_CONNECTION_LIMIT: PostgreSQL has reached its connection limit. Use the Neon pooled URL and check active connections.'
    if any(part in detail for part in ('quota', 'compute time', 'endpoint is disabled', 'compute is disabled', 'suspended')):
        return 'DB_SERVICE_LIMIT: The database service reports a quota or availability restriction. Check the Neon project status and usage.'
    if any(part in detail for part in ('invalid connection option', 'invalid uri', 'invalid percent-encoded', 'missing "="', 'invalid integer value')):
        return 'DB_URL: DATABASE_URL could not be parsed. Paste only the full PostgreSQL URL, without a command, quotes or extra text.'
    if any(part in detail for part in ('timeout', 'timed out')):
        return 'DB_TIMEOUT: The connection timed out. Check the Neon compute status, hostname and network availability, then retry.'
    if any(part in detail for part in ('connection refused', 'network is unreachable', 'no route to host')):
        return 'DB_NETWORK: The database endpoint could not be reached. Check the Neon hostname, port and compute status.'
    # libpq may mention SSL even when the underlying failure is a timeout or
    # a closed socket. Never treat the presence of "SSL" as a root cause.
    signatures = (
        ('DB_TLS_CERT', ('certificate verify failed', 'certificate has expired', 'self-signed certificate', 'unable to get local issuer'), 'TLS certificate verification failed.'),
        ('DB_TLS_UNSUPPORTED', ('does not support ssl', 'ssl is not enabled', 'ssl support is not compiled'), 'The client or server does not support the requested encrypted connection.'),
        ('DB_TLS_PROTOCOL', ('wrong version number', 'unsupported protocol', 'protocol version', 'no protocols available'), 'TLS protocol negotiation failed.'),
        ('DB_TLS_CIPHER', ('no shared cipher', 'no ciphers available', 'dh key too small', 'ee key too small', 'legacy sigalg'), 'TLS cipher or signature negotiation failed.'),
        ('DB_TLS_ALERT', ('handshake failure', 'tlsv1 alert', 'sslv3 alert', 'tls alert'), 'The peer rejected the TLS handshake.'),
        ('DB_CONNECTION_CLOSED', ('eof detected', 'unexpected eof', 'closed the connection', 'connection reset', 'broken pipe', 'connection has been closed'), 'The remote connection closed unexpectedly during connection setup.'),
        ('DB_TLS_SYSCALL', ('ssl syscall',), 'The TLS socket operation failed without a recognized close or timeout reason.'),
        ('DB_TLS_NEGOTIATION', ('invalid response to ssl negotiation', 'received invalid response to ssl'), 'The endpoint returned an invalid PostgreSQL SSL negotiation response.'),
    )
    for code, fragments, explanation in signatures:
        if any(fragment in detail for fragment in fragments):
            return f'{code}: {explanation} Keep the Neon SSL parameters; check the endpoint and deployment settings.'
    if any(part in detail for part in ('ssl', 'tls', 'certificate')):
        return 'DB_SSL_UNKNOWN: The driver reported an unrecognized SSL-related failure. Keep sslmode=require; further driver diagnostics are needed.'
    if state == '28000' or any(part in detail for part in ('no pg_hba', 'role', 'access denied')):
        return 'DB_ACCESS: PostgreSQL rejected access for the configured role. Check the role and connection settings in Neon.'
    code = f' SQLSTATE={state}.' if isinstance(state, str) and re.fullmatch(r'[A-Z0-9]{5}', state) else ''
    return 'DB_CONNECT: PostgreSQL connection failed. Check DATABASE_URL and the Neon project status.' + code


class Row(dict):
    """Named columns with positional access for existing aggregate queries."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def row_factory(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Row(zip(names, values))


def postgres_query(query):
    # Preserve quoted SQL literals/identifiers, including escaped quotes. The
    # application's SQL contains no comments, dollar quotes or JSON operators.
    tokens = re.split(r"('(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")", query)
    return ''.join(part.replace('%', '%%') if i % 2 else part.replace('%', '%%').replace('?', '%s')
                   for i, part in enumerate(tokens))


class PostgresConnection:
    dialect = 'postgres'

    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, parameters=None):
        if parameters is None:
            return self.connection.execute(query)
        return self.connection.execute(postgres_query(query), parameters)

    def executemany(self, query, parameters):
        cursor = self.connection.cursor()
        cursor.executemany(postgres_query(query), parameters)
        return cursor


def write_lock(conn):
    if getattr(conn, 'dialect', 'sqlite') == 'postgres':
        conn.execute('SELECT pg_advisory_xact_lock(?)', (WRITE_LOCK,))
    else:
        conn.execute('BEGIN IMMEDIATE')


def photo_columns(conn):
    if getattr(conn, 'dialect', 'sqlite') == 'postgres':
        return {row[0] for row in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='photos'")}
    return {row['name'] for row in conn.execute('PRAGMA table_info(photos)')}


class Database:
    def __init__(self, path):
        self.path = path
        self.url = os.environ.get('DATABASE_URL', '').strip()
        self.backend = 'postgres' if self.url else 'sqlite'
        if self.url and not self.url.startswith(('postgresql://', 'postgres://')):
            raise ValueError('DATABASE_URL must be a PostgreSQL connection URL.')
        if os.environ.get('RENDER') == 'true':
            if not self.url:
                raise ValueError('Render requires DATABASE_URL. SQLite on the local disk is not persistent.')
            if os.environ.get('EW_PHOTO_STORAGE', 'local') != 'r2':
                raise ValueError('Render requires EW_PHOTO_STORAGE=r2 to preserve uploaded photos.')

    @contextmanager
    def __call__(self):
        if self.backend == 'postgres':
            try:
                conn = psycopg.connect(self.url, connect_timeout=15, row_factory=row_factory,
                                       prepare_threshold=None)
            except psycopg.Error as error:
                raise RuntimeError(connection_failure(error)) from None
            with conn:
                conn.execute("SET LOCAL statement_timeout = '20s'")
                conn.execute("SET LOCAL lock_timeout = '15s'")
                yield PostgresConnection(conn)
        else:
            conn = sqlite3.connect(self.path, timeout=20)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA busy_timeout=20000')
            try:
                with conn:
                    yield conn
            finally:
                conn.close()

    def initialize(self, schema, migrate_roles, store, setup_file):
        if self.backend == 'sqlite':
            with self() as conn:
                conn.execute('PRAGMA journal_mode=WAL')
                conn.executescript(schema)
                migrate_roles(conn, store)
            if not setup_file.exists():
                import secrets
                try:
                    fd = os.open(setup_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    with os.fdopen(fd, 'w') as file:
                        file.write(secrets.token_urlsafe(32))
                except FileExistsError:
                    pass
            return setup_file.read_text().strip()

        import secrets
        schema = schema.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY')
        schema = re.sub(r'\bREAL\b', 'DOUBLE PRECISION', schema)
        with self() as conn:
            write_lock(conn)
            for statement in schema.split(';'):
                if statement.strip():
                    conn.execute(statement)
            conn.execute('CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            conn.execute("INSERT INTO app_settings(key,value) VALUES ('setup_token',?) ON CONFLICT(key) DO NOTHING", (secrets.token_urlsafe(32),))
            return conn.execute("SELECT value FROM app_settings WHERE key='setup_token'").fetchone()[0]
