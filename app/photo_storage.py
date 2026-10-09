"""Private photo storage backends: local disk for development and Cloudflare R2."""
from __future__ import annotations

import os
from pathlib import Path


class LocalPhotoStore:
    kind = 'local'

    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, content: bytes):
        (self.directory / key).write_bytes(content)

    def get(self, key: str) -> bytes | None:
        path = self.directory / key
        return path.read_bytes() if path.is_file() else None

    def delete(self, key: str):
        (self.directory / key).unlink(missing_ok=True)


class R2PhotoStore:
    kind = 'r2'

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as error:  # pragma: no cover - depends on deployment extras.
            raise RuntimeError(
                'R2 is configured, but boto3 is missing. Install requirements.txt.'
            ) from error
        self.bucket = bucket
        self.client = boto3.client(
            service_name='s3',
            endpoint_url=endpoint.rstrip('/'),
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='auto',
            config=Config(signature_version='s3v4', retries={'max_attempts': 3, 'mode': 'standard'}),
        )

    @staticmethod
    def object_key(filename: str) -> str:
        return 'photos/' + filename

    def put(self, key: str, content: bytes):
        self.client.put_object(
            Bucket=self.bucket,
            Key=self.object_key(key),
            Body=content,
            ContentType='image/jpeg',
            CacheControl='private, no-store',
        )

    def get(self, key: str) -> bytes | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.object_key(key))
            return response['Body'].read()
        except self.client.exceptions.NoSuchKey:
            return None
        except Exception as error:
            status = getattr(error, 'response', {}).get('ResponseMetadata', {}).get('HTTPStatusCode')
            if status == 404:
                return None
            raise

    def delete(self, key: str):
        self.client.delete_object(Bucket=self.bucket, Key=self.object_key(key))


def create_photo_store(local_directory: Path):
    # Reuse the secrets already saved on Render without copying them into files.
    names = ('R2_ENDPOINT_URL', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET')
    values = {name: (os.environ.get(name, '').strip() or
                     os.environ.get('EW_' + name, '').strip()) for name in names}
    if not any(values.values()):
        if os.environ.get('EW_PHOTO_STORAGE') == 'r2' or os.environ.get('RENDER') == 'true':
            raise RuntimeError('Render requires a complete private R2 configuration; local uploads are not persistent.')
        return LocalPhotoStore(local_directory)
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError('Incomplete R2 configuration. Missing: ' + ', '.join(missing))
    if not values['R2_ENDPOINT_URL'].startswith('https://'):
        raise RuntimeError('R2_ENDPOINT_URL must use HTTPS.')
    return R2PhotoStore(
        values['R2_ENDPOINT_URL'],
        values['R2_ACCESS_KEY_ID'],
        values['R2_SECRET_ACCESS_KEY'],
        values['R2_BUCKET'],
    )
