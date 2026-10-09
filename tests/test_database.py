import pytest
from app.database import Database, postgres_query
from app.server import create_app


def test_render_refuses_ephemeral_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(ValueError, match='Render requires DATABASE_URL'):
        Database(tmp_path/'jobs.sqlite3')


def test_render_requires_remote_photos(monkeypatch, tmp_path):
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://example/test')
    monkeypatch.setenv('EW_PHOTO_STORAGE', 'local')
    with pytest.raises(ValueError, match='EW_PHOTO_STORAGE=r2'):
        Database(tmp_path/'jobs.sqlite3')


def test_invalid_url_never_falls_back_to_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_URL', 'https://invalid.test/secret')
    with pytest.raises(ValueError, match='PostgreSQL connection URL'):
        create_app(tmp_path)
    assert not (tmp_path/'jobs.sqlite3').exists()


def test_query_parameters_keep_literals_and_percent_signs():
    query = '''SELECT 'Why? 50%', 'it''s?', "field?", 7 % 2 WHERE email=?'''
    assert postgres_query(query) == '''SELECT 'Why? 50%%', 'it''s?', "field?", 7 %% 2 WHERE email=%s'''


def test_schema_name_cannot_be_sql_injection(monkeypatch, tmp_path):
    monkeypatch.setenv('EW_DB_SCHEMA', 'app_private; DROP SCHEMA public')
    with pytest.raises(ValueError, match='EW_DB_SCHEMA'):
        Database(tmp_path/'jobs.sqlite3')


def test_render_defaults_to_private_schema(monkeypatch, tmp_path):
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://example/test')
    monkeypatch.setenv('EW_PHOTO_STORAGE', 'r2')
    assert Database(tmp_path/'jobs.sqlite3').schema == 'app_private'


class PrivateSchemaConnection:
    def __init__(self, missing=False):
        self.queries = []
        self.missing = missing
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, parameters=None):
        self.queries.append((query, parameters))
        if 'to_regclass' in query:
            self.result = (None if self.missing else parameters[0],)
        elif "SELECT value FROM app_settings" in query:
            self.result = ('persistent-private-token',)
        return self

    def fetchone(self):
        return self.result


def test_supabase_schema_uses_migrations_not_runtime_ddl(monkeypatch, tmp_path):
    import psycopg
    monkeypatch.setenv('DATABASE_URL', 'postgresql://example/test')
    monkeypatch.setenv('EW_DB_SCHEMA', 'app_private')
    raw = PrivateSchemaConnection()
    monkeypatch.setattr(psycopg, 'connect', lambda *args, **kwargs: raw)
    db = Database(tmp_path/'jobs.sqlite3')
    assert db.initialize('CREATE TABLE public.nope (id int)', None, tmp_path, tmp_path/'.setup-token') == 'persistent-private-token'
    assert raw.queries[0][0] == 'SET LOCAL search_path TO app_private, pg_catalog'
    assert sum('to_regclass' in query for query, _ in raw.queries) == 10
    assert not any(query.startswith(('CREATE', 'ALTER')) for query, _ in raw.queries)


def test_supabase_missing_migration_fails_closed(monkeypatch, tmp_path):
    import psycopg
    monkeypatch.setenv('DATABASE_URL', 'postgresql://example/test')
    monkeypatch.setenv('EW_DB_SCHEMA', 'app_private')
    monkeypatch.setattr(psycopg, 'connect', lambda *args, **kwargs: PrivateSchemaConnection(missing=True))
    db = Database(tmp_path/'jobs.sqlite3')
    with pytest.raises(RuntimeError, match='Supabase migrations'):
        db.initialize('', None, tmp_path, tmp_path/'.setup-token')
