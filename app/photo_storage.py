"""Private photo storage. Legacy filenames always resolve to the local uploads folder."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.responses import FileResponse, RedirectResponse

logger = logging.getLogger(__name__)
_FILENAME = re.compile(r'[a-f0-9]{48}\.(?:jpg|webp)\Z')


class PhotoMissing(Exception):
    pass


class StorageUnavailable(Exception):
    def __init__(self, message, cleanup_failed=False):
        super().__init__(message)
        self.cleanup_failed = cleanup_failed


class PhotoStorage:
    def __init__(self, uploads: Path):
        self.uploads = uploads
        self.backend = os.environ.get('EW_PHOTO_STORAGE', 'local').strip().lower()
        if self.backend not in ('local', 'r2'):
            raise ValueError('EW_PHOTO_STORAGE must be local or r2.')
        self.client = None
        self.image_origin = ''
        if self.backend == 'r2':
            required = ('EW_R2_ENDPOINT_URL', 'EW_R2_BUCKET', 'EW_R2_ACCESS_KEY_ID', 'EW_R2_SECRET_ACCESS_KEY')
            missing = [key for key in required if not os.environ.get(key, '').strip()]
            if missing:
                raise ValueError('Missing R2 configuration: ' + ', '.join(missing))
            endpoint = os.environ['EW_R2_ENDPOINT_URL'].strip().rstrip('/')
            parts = urlsplit(endpoint)
            if (parts.scheme != 'https' or not parts.hostname
                    or not re.fullmatch(r'[a-f0-9]{32}(?:\.(?:eu|us|fedramp))?\.r2\.cloudflarestorage\.com', parts.hostname)
                    or parts.username or parts.password or parts.port or parts.path or parts.query or parts.fragment):
                raise ValueError('EW_R2_ENDPOINT_URL must be the HTTPS S3 endpoint copied from Cloudflare R2.')
            self.image_origin = endpoint
            self.bucket = os.environ['EW_R2_BUCKET'].strip()
            self.prefix = os.environ.get('EW_R2_PREFIX', '18wheelers/photos').strip('/')
            if not re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', self.prefix):
                raise ValueError('EW_R2_PREFIX must contain safe folder names separated by /.')
            self.ttl = int(os.environ.get('EW_R2_URL_TTL_SECONDS', '300'))
            if not 60 <= self.ttl <= 900:
                raise ValueError('EW_R2_URL_TTL_SECONDS must be between 60 and 900.')
            import boto3
            from botocore.config import Config
            self.client = boto3.client(
                's3', endpoint_url=endpoint, region_name='auto',
                aws_access_key_id=os.environ['EW_R2_ACCESS_KEY_ID'],
                aws_secret_access_key=os.environ['EW_R2_SECRET_ACCESS_KEY'],
                config=Config(signature_version='s3v4', s3={'addressing_style': 'path'},
                              connect_timeout=5, read_timeout=20, retries={'max_attempts': 2},
                              request_checksum_calculation='when_required',
                              response_checksum_validation='when_required'),
            )

    @staticmethod
    def _filename(filename: str) -> str:
        if not _FILENAME.fullmatch(filename):
            raise PhotoMissing('Invalid photo filename.')
        return filename

    def _key(self, reference: str) -> str:
        if self.client is None:
            raise StorageUnavailable('R2 is not configured.')
        key = reference[3:]
        if not key.startswith(self.prefix + '/'):
            raise PhotoMissing('Invalid photo key.')
        self._filename(key[len(self.prefix) + 1:])
        return key

    @staticmethod
    def _media_type(reference: str) -> str:
        return 'image/webp' if reference.endswith('.webp') else 'image/jpeg'

    def put(self, filename: str, content: bytes) -> str:
        filename = self._filename(filename)
        if self.backend == 'local':
            try:
                (self.uploads / filename).write_bytes(content)
            except OSError:
                cleaned = self.cleanup(filename)
                raise StorageUnavailable('Photo storage is temporarily unavailable.', cleanup_failed=not cleaned) from None
            return filename
        key = self.prefix + '/' + filename
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content,
                                   ContentType=self._media_type(filename), CacheControl='private, no-store')
        except Exception:
            # A timeout can occur after the server accepted the object.
            cleaned = self.cleanup('r2:' + key)
            raise StorageUnavailable('Photo storage is temporarily unavailable.', cleanup_failed=not cleaned) from None
        return 'r2:' + key

    def response(self, reference: str):
        if not reference.startswith('r2:'):
            path = self.uploads / self._filename(reference)
            if not path.is_file():
                raise PhotoMissing('Photo file not found. Check the server backup.')
            return FileResponse(path, media_type=self._media_type(reference))
        key = self._key(reference)
        from botocore.exceptions import ClientError
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            url = self.client.generate_presigned_url(
                'get_object', Params={'Bucket': self.bucket, 'Key': key,
                                     'ResponseContentType': self._media_type(reference),
                                     'ResponseCacheControl': 'private, no-store'},
                ExpiresIn=self.ttl,
            )
        except ClientError as exc:
            if str(exc.response.get('Error', {}).get('Code')) in ('404', 'NoSuchKey', 'NotFound'):
                raise PhotoMissing('Photo file not found. Check the storage backup.') from None
            raise StorageUnavailable('Photo storage is temporarily unavailable.') from None
        except Exception:
            raise StorageUnavailable('Photo storage is temporarily unavailable.') from None
        return RedirectResponse(url, status_code=307, headers={'Cache-Control': 'no-store'})

    def delete(self, reference: str) -> None:
        if not reference.startswith('r2:'):
            (self.uploads / self._filename(reference)).unlink(missing_ok=True)
            return
        key = self._key(reference)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception:
            raise StorageUnavailable('Photo storage is temporarily unavailable.') from None

    def cleanup(self, reference: str) -> bool:
        try:
            self.delete(reference)
            return True
        except Exception:
            # Never log credentials or signed URLs; preserve the original error.
            logger.warning('Photo rollback cleanup failed; check storage for orphan objects.')
            return False
