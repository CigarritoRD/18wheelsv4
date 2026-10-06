"""Run with EW_TEST_POSTGRES_URL pointing to a disposable test database.

Every test creates a separate schema and drops only that schema. Never use a
production URL. Existing behavior tests run unchanged against PostgreSQL.
"""
import os
import secrets
from concurrent.futures import ThreadPoolExecutor

import psycopg
from psycopg import sql
import pytest
from fastapi.testclient import TestClient
from app.server import create_app
from test_app import ADMIN_PASSWORD, send, new_job, upload
import test_app as base
import test_photo_limits as quotas
import test_three_roles as roles
import test_r2_storage as remote
from test_r2_storage import r2_env

URL = os.environ.get('EW_TEST_POSTGRES_URL')
pytestmark = pytest.mark.skipif(not URL, reason='Set EW_TEST_POSTGRES_URL for PostgreSQL integration tests')


@pytest.fixture
def pg_database(monkeypatch):
    schema = 'ew_test_' + secrets.token_hex(8)
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    # Keep a URL in DATABASE_URL, adding the schema as a libpq options parameter.
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    parts = urlsplit(URL)
    query = dict(parse_qsl(parts.query))
    query['options'] = '-csearch_path='+schema
    test_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))
    monkeypatch.setenv('DATABASE_URL', test_url)
    monkeypatch.delenv('RENDER', raising=False)
    yield test_url
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


@pytest.fixture
def workspace(pg_database, tmp_path):
    app = create_app(tmp_path)
    client = TestClient(app)
    response = send(client, 'POST', '/api/setup', {
        'name':'Manager', 'email':'manager@example.test', 'password':ADMIN_PASSWORD,
        'setup_token':app.state.setup_token})
    assert response.status_code == 200, response.text
    yield app, client, tmp_path
    client.close()


@pytest.fixture
def r2_workspace(pg_database, tmp_path, monkeypatch, r2_env):
    import boto3
    s3 = remote.MemoryS3()
    monkeypatch.setattr(boto3, 'client', lambda *args, **kwargs: s3)
    app = create_app(tmp_path)
    client = TestClient(app)
    result = send(client, 'POST', '/api/setup', {
        'name':'Manager', 'email':'manager@example.test', 'password':ADMIN_PASSWORD,
        'setup_token':app.state.setup_token})
    assert result.status_code == 200, result.text
    yield app, client, s3, tmp_path
    client.close()


# Exercise all workspace-based account/job/role/quota behavior on PostgreSQL.
for module in (base, quotas, roles):
    import inspect
    for name, function in vars(module).items():
        if name.startswith('test_') and callable(function) and 'workspace' in inspect.signature(function).parameters:
            globals()[name] = function

for name, function in vars(remote).items():
    if name.startswith('test_') and callable(function) and 'r2_workspace' in inspect.signature(function).parameters:
        globals()[name] = function


def test_setup_token_is_persistent_and_initialization_is_concurrent(pg_database, tmp_path):
    with ThreadPoolExecutor(max_workers=2) as pool:
        apps = list(pool.map(lambda i: create_app(tmp_path/str(i)), range(2)))
    assert apps[0].state.setup_token == apps[1].state.setup_token
    assert not (tmp_path/'0'/'jobs.sqlite3').exists()


def test_empty_local_directory_preserves_users_jobs_sessions_and_reservations(workspace, tmp_path):
    app, client, old_dir = workspace
    job = new_job(client)
    token = app.state.photo_limits.reserve(job['id'], [200])
    app.state.photo_limits.upload_attempt(1)
    restarted = create_app(tmp_path/'empty-render-disk')
    assert restarted.state.setup_token == app.state.setup_token
    reconnected = TestClient(restarted)
    reconnected.cookies.update(client.cookies)
    assert reconnected.get('/api/session').json()['needs_setup'] is False
    assert reconnected.get('/api/jobs').json()['jobs'][0]['id'] == job['id']
    assert restarted.state.photo_limits.usage()['reserved_bytes'] == 200
    with restarted.state.db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM photo_counters').fetchone()[0] == 3
    restarted.state.photo_limits.release(token)


def test_bigint_capacity_and_float_expiry_keep_precision(workspace):
    app, client, _ = workspace
    job = new_job(client)
    app.state.photo_limits.reserve(job['id'], [3 * 1024**3])
    usage = client.get('/api/storage/usage').json()
    assert usage['reserved_bytes'] == 3 * 1024**3
    with app.state.db() as conn:
        row = conn.execute('SELECT expires FROM sessions WHERE user_id=1').fetchone()
        assert row[0] > 1_000_000_000
        assert row[0] != int(row[0])


def test_duplicate_email_rolls_back_and_connection_recovers(workspace):
    _, client, _ = workspace
    base.add_employee(client)
    result = send(client, 'POST', '/api/users', {'name':'Duplicate', 'email':'carlos@example.test',
                  'role':'technician', 'password':base.TEMP_PASSWORD})
    assert result.status_code == 409
    assert client.get('/api/users').status_code == 200


def test_postgres_values_and_literals_are_parameterized(workspace):
    app, client, _ = workspace
    title = "50%? O'Brien; DROP TABLE jobs;"
    job = new_job(client, title=title)
    assert client.get(f'/api/jobs/{job["id"]}').json()['job']['title'] == title
    with app.state.db() as conn:
        row = conn.execute("SELECT 'Why? 50%' AS literal, ? AS value", (title,)).fetchone()
        assert row['literal'] == 'Why? 50%'
        assert row['value'] == title


def test_only_one_admin_setup_can_commit_concurrently(pg_database, tmp_path):
    app = create_app(tmp_path)
    clients = [TestClient(app), TestClient(app)]
    for client in clients:
        client.get('/api/session')
    def setup(index):
        return send(clients[index], 'POST', '/api/setup', {
            'name':'Manager', 'email':f'manager{index}@example.test',
            'password':ADMIN_PASSWORD, 'setup_token':app.state.setup_token}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(setup, range(2))) == [200, 409]
    with app.state.db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 1
    for client in clients:
        client.close()
