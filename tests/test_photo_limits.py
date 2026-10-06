import concurrent.futures
import io
import pytest
from fastapi import HTTPException
from PIL import Image
from app.photo_processing import compress_photo
from test_app import workspace, send, new_job, upload, image_bytes, employee_client


def test_webp_compression_caps_size_dimensions_and_strips_metadata():
    source = Image.new('RGB', (3000, 2000), 'blue')
    exif = source.getexif(); exif[0x010E] = 'private metadata'
    raw = io.BytesIO(); source.save(raw, 'JPEG', exif=exif)
    content = compress_photo(raw.getvalue(), 300*1024, 1600, 80)
    assert len(content) <= 300*1024
    with Image.open(io.BytesIO(content)) as image:
        assert image.format == 'WEBP'
        assert max(image.size) <= 1600
        assert not image.getexif()
        assert not image.info.get('xmp')


def test_noisy_photo_fits_stored_byte_cap():
    image = Image.effect_noise((1800, 1800), 100).convert('RGB')
    raw = io.BytesIO(); image.save(raw, 'PNG')
    content = compress_photo(raw.getvalue(), 100*1024, 1600, 80)
    assert len(content) <= 100*1024
    assert Image.open(io.BytesIO(content)).format == 'WEBP'


def test_user_rate_limit_and_invalid_uploads_count(workspace):
    _, client, _ = workspace
    job = new_job(client)
    for _ in range(3):
        assert upload(client, job['id'], b'invalid').status_code == 400
    response = upload(client, job['id'])
    assert response.status_code == 429
    assert int(response.headers['retry-after']) > 0


def test_capacity_rejected_before_storage_call_and_delete_frees_space(workspace, monkeypatch):
    app, client, _ = workspace
    job = new_job(client)
    compressed = compress_photo(image_bytes(), 300*1024, 1600, 80)
    app.state.photo_limits.total_limit = len(compressed)
    assert upload(client, job['id']).status_code == 200
    response = upload(client, job['id'])
    assert response.status_code == 413
    assert app.state.photo_limits.usage()['stored_bytes'] == len(compressed)
    photo = client.get(f'/api/jobs/{job["id"]}').json()['photos'][0]
    assert send(client, 'DELETE', f'/api/photos/{photo["id"]}').status_code == 200
    assert app.state.photo_limits.usage()['stored_bytes'] == 0
    assert upload(client, job['id']).status_code == 200


def test_concurrent_reservations_cannot_exceed_capacity(workspace):
    app, client, _ = workspace
    job = new_job(client)
    limits = app.state.photo_limits
    limits.total_limit = 100
    def reserve():
        try:
            return limits.reserve(job['id'], [60])
        except HTTPException as exc:
            return exc.status_code
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: reserve(), range(2)))
    assert sum(isinstance(r, str) for r in results) == 1
    assert results.count(413) == 1
    assert limits.usage()['reserved_bytes'] == 60
    for token in results:
        if isinstance(token, str): limits.release(token)
    assert limits.usage()['reserved_bytes'] == 0


def test_per_job_limit_and_daily_upload_limit(workspace):
    app, client, _ = workspace
    job = new_job(client)
    app.state.photo_limits.per_job = 1
    assert upload(client, job['id']).status_code == 200
    assert upload(client, job['id']).status_code == 413
    app.state.photo_limits.user_daily = 2
    assert upload(client, job['id']).status_code == 429


def test_two_processing_slots_reject_more_work(workspace):
    app, _, _ = workspace
    limits = app.state.photo_limits
    with limits.processing(), limits.processing():
        with pytest.raises(HTTPException) as error:
            with limits.processing(): pass
        assert error.value.status_code == 429
    with limits.processing(): pass


def test_storage_usage_is_admin_only(workspace):
    app, manager, _ = workspace
    employee, _ = employee_client(app, manager)
    assert manager.get('/api/storage/usage').status_code == 200
    assert employee.get('/api/storage/usage').status_code == 403
    assert manager.get('/api/storage/usage').json()['limit_bytes'] == 5000*1024*1024


def test_reservations_persist_after_restart(workspace):
    app, manager, folder = workspace
    job = new_job(manager)
    token = app.state.photo_limits.reserve(job['id'], [250])
    from app.server import create_app
    restarted = create_app(folder)
    assert restarted.state.photo_limits.usage()['reserved_bytes'] == 250
    restarted.state.photo_limits.release(token)


def test_photo_reads_are_throttled(workspace):
    app, client, _ = workspace
    job = new_job(client)
    assert upload(client, job['id']).status_code == 200
    photo = client.get(f'/api/jobs/{job["id"]}').json()['photos'][0]
    app.state.photo_limits.read_user_minute = 1
    assert client.get(photo['url']).status_code == 200
    assert client.get(photo['url']).status_code == 429
