"""Cloud adapter tests that do not require live Supabase or R2 accounts."""
import pytest

from app.database import Database, PostgresConnection, connection_failure
from app.photo_storage import R2PhotoStore, create_photo_store


class FakeBody:
    def __init__(self, content):self.content=content
    def read(self):return self.content


class FakeR2Client:
    class exceptions:
        class NoSuchKey(Exception):pass

    def __init__(self):self.calls=[]
    def put_object(self,**kwargs):self.calls.append(('put',kwargs))
    def get_object(self,**kwargs):
        self.calls.append(('get',kwargs))
        return {'Body':FakeBody(b'jpeg')}
    def delete_object(self,**kwargs):self.calls.append(('delete',kwargs))


def test_r2_store_uses_private_photo_prefix_and_metadata():
    store=R2PhotoStore.__new__(R2PhotoStore)
    store.bucket='private-bucket'
    store.client=FakeR2Client()
    store.put('abc.jpg',b'jpeg')
    assert store.get('abc.jpg')==b'jpeg'
    store.delete('abc.jpg')
    put=store.client.calls[0][1]
    assert put['Bucket']=='private-bucket' and put['Key']=='photos/abc.jpg'
    assert put['ContentType']=='image/jpeg' and put['CacheControl']=='private, no-store'
    assert [call[1]['Key'] for call in store.client.calls]==['photos/abc.jpg']*3


def test_partial_r2_configuration_fails_closed(monkeypatch,tmp_path):
    for name in ('R2_ENDPOINT_URL','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_BUCKET'):
        monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv('R2_BUCKET','configured-without-credentials')
    with pytest.raises(RuntimeError,match='Incomplete R2 configuration'):
        create_photo_store(tmp_path)


def test_postgres_adapter_converts_application_placeholders():
    assert PostgresConnection._sql('SELECT * FROM jobs WHERE id=? AND archived=?') == (
        'SELECT * FROM jobs WHERE id=%s AND archived=%s'
    )


def test_postgres_sql_keeps_quoted_question_marks_and_escapes_percent():
    assert PostgresConnection._sql("SELECT '?' WHERE title LIKE ? AND note='100%'") == (
        "SELECT '?' WHERE title LIKE %s AND note='100%%'"
    )


def test_render_r2_aliases_reuse_existing_environment(monkeypatch, tmp_path):
    import app.photo_storage as storage
    values = {'R2_ENDPOINT_URL': 'https://example.r2.cloudflarestorage.com',
              'R2_ACCESS_KEY_ID': 'test-key', 'R2_SECRET_ACCESS_KEY': 'test-secret',
              'R2_BUCKET': 'private-bucket'}
    for name, value in values.items():
        monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv('EW_' + name, value)
    monkeypatch.setattr(storage, 'R2PhotoStore', lambda *args: args)
    assert create_photo_store(tmp_path) == tuple(values.values())


def test_render_r2_fails_closed_without_secrets(monkeypatch, tmp_path):
    for name in ('R2_ENDPOINT_URL', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET'):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv('EW_' + name, raising=False)
    monkeypatch.setenv('RENDER', 'true')
    with pytest.raises(RuntimeError, match='complete private R2 configuration'):
        create_photo_store(tmp_path)


def test_render_requires_postgres(monkeypatch, tmp_path):
    monkeypatch.setenv('RENDER', 'true')
    with pytest.raises(RuntimeError, match='requires DATABASE_URL'):
        Database(tmp_path / 'jobs.sqlite3')


@pytest.mark.parametrize('detail,code', [
    ('SSL connection has been closed unexpectedly', 'DB_CONNECTION_CLOSED'),
    ('TLS alert internal error', 'DB_TLS_INTERNAL'),
    ('invalid sslmode value', 'DB_URL'),
    ('password authentication failed', 'DB_AUTH'),
    ('certificate verify failed', 'DB_TLS_CERT'),
    ('unknown SSL error', 'DB_CONNECT'),
])
def test_connection_diagnostics_never_emit_arbitrary_driver_text(detail, code):
    result = connection_failure(RuntimeError(detail + ' secret=do-not-log-this-password'))
    assert result.startswith(code + ':')
    assert 'do-not-log-this-password' not in result


def test_safe_pool_connection_does_not_log_original_error(monkeypatch):
    import psycopg
    from app.database import SafePostgresConnection
    def broken_connect(cls, *args, **kwargs):
        raise psycopg.OperationalError('SSL connection has been closed unexpectedly secret=private')
    monkeypatch.setattr(psycopg.Connection, 'connect', classmethod(broken_connect))
    with pytest.raises(psycopg.OperationalError) as captured:
        SafePostgresConnection.connect('unused-test-connection')
    assert 'DB_CONNECTION_CLOSED' in str(captured.value)
    assert 'secret=private' not in str(captured.value)
