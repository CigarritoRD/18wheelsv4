"""R2 tests with an in-memory S3 double; no cloud account required."""
import io
from urllib.parse import parse_qs, urlsplit
import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from fastapi.testclient import TestClient
from PIL import Image
from app.photo_storage import PhotoStorage, PhotoMissing, StorageUnavailable
from app.server import create_app
from test_app import send, new_job, upload, employee_client, ADMIN_PASSWORD, image_bytes

ENDPOINT = 'https://' + 'a' * 32 + '.r2.cloudflarestorage.com'

class MemoryS3:
    def __init__(self):
        self.objects = {}
        self.heads = 0
        self.puts = 0
        self.fail_put_at = None
        self.fail_delete = False
    def put_object(self, **kwargs):
        self.puts += 1
        if self.puts == self.fail_put_at:
            raise OSError('connection lost')
        self.objects[kwargs['Key']] = kwargs
        return {}
    def head_object(self, **kwargs):
        self.heads += 1
        if kwargs['Key'] not in self.objects:
            raise ClientError({'Error': {'Code': '404'}}, 'HeadObject')
        return {}
    def generate_presigned_url(self, operation, Params, ExpiresIn):
        assert operation == 'get_object' and ExpiresIn == 300
        return ENDPOINT + '/photos/' + Params['Key'] + '?signed=test'
    def delete_object(self, **kwargs):
        if self.fail_delete:
            raise OSError('connection lost')
        self.objects.pop(kwargs['Key'], None)
        return {}

@pytest.fixture
def r2_env(monkeypatch):
    for key, value in {
        'EW_PHOTO_STORAGE': 'r2', 'EW_R2_ENDPOINT_URL': ENDPOINT,
        'EW_R2_BUCKET': 'photos', 'EW_R2_ACCESS_KEY_ID': 'test-access-key',
        'EW_R2_SECRET_ACCESS_KEY': 'test-secret-key',
    }.items():
        monkeypatch.setenv(key, value)

@pytest.fixture
def r2_workspace(tmp_path, monkeypatch, r2_env):
    s3 = MemoryS3()
    monkeypatch.setattr(boto3, 'client', lambda *args, **kwargs: s3)
    app = create_app(tmp_path)
    client = TestClient(app)
    result = send(client, 'POST', '/api/setup', {
        'name': 'Manager', 'email': 'manager@example.test', 'password': ADMIN_PASSWORD,
        'setup_token': (tmp_path / '.setup-token').read_text(),
    })
    assert result.status_code == 200
    return app, client, s3, tmp_path


def test_r2_upload_permission_redirect_and_delete(r2_workspace):
    app, manager, s3, folder = r2_workspace
    employee, _ = employee_client(app, manager)
    job = new_job(manager)
    assert upload(manager, job['id']).status_code == 200
    photo = manager.get(f'/api/jobs/{job["id"]}').json()['photos'][0]
    with app.state.db() as conn:
        reference = conn.execute('SELECT filename FROM photos').fetchone()[0]
    assert reference.startswith('r2:18wheelers/photos/')
    assert list((folder / 'uploads').iterdir()) == []
    obj = s3.objects[reference[3:]]
    assert obj['ContentType'] == 'image/webp'
    with Image.open(io.BytesIO(obj['Body'])) as decoded:
        assert decoded.format == 'WEBP'
    assert len(obj['Body']) <= app.state.photo_limits.max_stored
    with Image.open(io.BytesIO(obj['Body'])) as image:
        assert not image.getexif()
    assert TestClient(app).get(photo['url'], follow_redirects=False).status_code == 401
    assert employee.get(photo['url'], follow_redirects=False).status_code == 404
    assert s3.heads == 0
    response = manager.get(photo['url'], follow_redirects=False)
    assert response.status_code == 307
    assert response.headers['location'].startswith(ENDPOINT)
    assert response.headers['cache-control'] == 'no-store'
    assert ENDPOINT in manager.get('/').headers['content-security-policy']
    assert send(manager, 'DELETE', f'/api/photos/{photo["id"]}').status_code == 200
    assert not s3.objects
    assert manager.get(photo['url'], follow_redirects=False).status_code == 404


def test_failed_batch_cleans_objects_and_does_not_insert_rows(r2_workspace):
    app, manager, s3, _ = r2_workspace
    job = new_job(manager)
    s3.fail_put_at = 2
    csrf = manager.get('/api/session').json()['csrf']
    result = manager.post(f'/api/jobs/{job["id"]}/photos', headers={'x-csrf-token': csrf},
                          data={'phase': 'Before'}, files=[
                              ('files', ('one.jpg', image_bytes(), 'image/jpeg')),
                              ('files', ('two.jpg', image_bytes(), 'image/jpeg'))])
    assert result.status_code == 503
    assert not s3.objects
    with app.state.db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM photos').fetchone()[0] == 0


def test_failed_delete_keeps_photo_record_for_retry(r2_workspace):
    _, manager, s3, _ = r2_workspace
    job = new_job(manager)
    assert upload(manager, job['id']).status_code == 200
    photo = manager.get(f'/api/jobs/{job["id"]}').json()['photos'][0]
    s3.fail_delete = True
    assert send(manager, 'DELETE', f'/api/photos/{photo["id"]}').status_code == 503
    assert len(manager.get(f'/api/jobs/{job["id"]}').json()['photos']) == 1
    assert len(s3.objects) == 1


def test_missing_r2_object_is_404(r2_workspace):
    _, manager, s3, _ = r2_workspace
    job = new_job(manager)
    assert upload(manager, job['id']).status_code == 200
    photo = manager.get(f'/api/jobs/{job["id"]}').json()['photos'][0]
    s3.objects.clear()
    assert manager.get(photo['url'], follow_redirects=False).status_code == 404


def test_legacy_local_photos_still_work_with_r2(r2_workspace):
    app, _, s3, folder = r2_workspace
    name = 'b' * 48 + '.jpg'
    (folder / 'uploads' / name).write_bytes(b'legacy')
    response = app.state.photo_storage.response(name)
    assert response.path == folder / 'uploads' / name
    app.state.photo_storage.delete(name)
    assert not (folder / 'uploads' / name).exists()
    assert s3.heads == 0


def test_real_boto_calls_and_signed_url(tmp_path, r2_env):
    storage = PhotoStorage(tmp_path)
    name = 'c' * 48 + '.jpg'
    key = '18wheelers/photos/' + name
    with Stubber(storage.client) as stub:
        stub.add_response('put_object', {}, {'Bucket': 'photos', 'Key': key, 'Body': b'jpeg',
                          'ContentType': 'image/jpeg', 'CacheControl': 'private, no-store'})
        stub.add_response('head_object', {}, {'Bucket': 'photos', 'Key': key})
        stub.add_response('delete_object', {}, {'Bucket': 'photos', 'Key': key})
        reference = storage.put(name, b'jpeg')
        response = storage.response(reference)
        url = urlsplit(response.headers['location'])
        query = parse_qs(url.query)
        assert url.scheme == 'https'
        assert query['X-Amz-Expires'] == ['300']
        assert query['X-Amz-Algorithm'] == ['AWS4-HMAC-SHA256']
        assert 'X-Amz-Signature' in query
        storage.delete(reference)
        stub.assert_no_pending_responses()


@pytest.mark.parametrize('key,value', [
    ('EW_PHOTO_STORAGE', 'typo'), ('EW_R2_ENDPOINT_URL', 'https://example.com'),
    ('EW_R2_ENDPOINT_URL', ENDPOINT + '/bad'), ('EW_R2_URL_TTL_SECONDS', '99999'),
    ('EW_R2_PREFIX', '../unsafe'),
])
def test_invalid_configuration_fails_at_startup(tmp_path, monkeypatch, r2_env, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        PhotoStorage(tmp_path)


def test_missing_credentials_fail_at_startup(tmp_path, monkeypatch, r2_env):
    monkeypatch.delenv('EW_R2_SECRET_ACCESS_KEY')
    with pytest.raises(ValueError, match='EW_R2_SECRET_ACCESS_KEY'):
        PhotoStorage(tmp_path)


def test_local_references_cannot_escape_uploads(tmp_path, monkeypatch):
    monkeypatch.setenv('EW_PHOTO_STORAGE', 'local')
    storage = PhotoStorage(tmp_path)
    with pytest.raises(PhotoMissing):
        storage.response('../private.txt')
    with pytest.raises(StorageUnavailable):
        storage.response('r2:18wheelers/photos/' + 'a' * 48 + '.jpg')


def test_cleanup_failure_keeps_capacity_reserved(r2_workspace):
    app, manager, s3, _ = r2_workspace
    job = new_job(manager)
    s3.fail_put_at = 2
    s3.fail_delete = True
    csrf = manager.get('/api/session').json()['csrf']
    response = manager.post(f'/api/jobs/{job["id"]}/photos', headers={'x-csrf-token': csrf},
                            data={'phase': 'Before'}, files=[
                                ('files', ('one.jpg', image_bytes(), 'image/jpeg')),
                                ('files', ('two.jpg', image_bytes(), 'image/jpeg'))])
    assert response.status_code == 503
    usage = app.state.photo_limits.usage()
    assert usage['stored_bytes'] == 0
    assert usage['reserved_bytes'] > 0
    assert s3.objects  # orphan is still charged against the app's capacity
    app.state.photo_limits.total_limit = usage['reserved_bytes']
    s3.fail_put_at = None; s3.fail_delete = False
    assert upload(manager, job['id']).status_code == 413


def test_oversized_quota_never_contacts_r2(r2_workspace):
    app, manager, s3, _ = r2_workspace
    job = new_job(manager)
    app.state.photo_limits.total_limit = 1
    assert upload(manager, job['id']).status_code == 413
    assert s3.puts == 0
    assert not s3.objects


def test_permission_change_during_upload_cleans_object_and_reservation(r2_workspace, monkeypatch):
    app, manager, s3, _ = r2_workspace
    employee, account = employee_client(app, manager)
    job = new_job(manager, assignee_id=account['id'])
    original_put = s3.put_object
    def put_and_unassign(**kwargs):
        result = original_put(**kwargs)
        with app.state.db() as conn:
            conn.execute('UPDATE jobs SET assignee_id=NULL WHERE id=?', (job['id'],))
        return result
    monkeypatch.setattr(s3, 'put_object', put_and_unassign)
    assert upload(employee, job['id']).status_code == 404
    assert not s3.objects
    assert app.state.photo_limits.usage()['reserved_bytes'] == 0


@pytest.mark.parametrize('jurisdiction', ['eu', 'us', 'fedramp'])
def test_jurisdiction_endpoints_are_supported(tmp_path, r2_env, monkeypatch, jurisdiction):
    endpoint = 'https://' + 'a' * 32 + '.' + jurisdiction + '.r2.cloudflarestorage.com'
    monkeypatch.setenv('EW_R2_ENDPOINT_URL', endpoint)
    storage = PhotoStorage(tmp_path)
    assert storage.image_origin == endpoint
