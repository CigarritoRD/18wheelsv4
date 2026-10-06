"""Bounded image decoding and WebP compression before cloud upload."""
import io
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException

Image.MAX_IMAGE_PIXELS = 24_000_000


def compress_photo(raw: bytes, max_bytes: int, max_dimension: int, quality: int) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise HTTPException(400, 'Use JPG, PNG or WebP images. Convert HEIC photos to JPG first.')
                source.load()
                image = ImageOps.exif_transpose(source)
                if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                    rgba = image.convert('RGBA')
                    image = Image.new('RGB', rgba.size, 'white')
                    image.paste(rgba, mask=rgba.getchannel('A'))
                else:
                    image = image.convert('RGB')
                image.info.clear()
                # Bound both stored bytes and encoder work: at most six attempts.
                sizes = (max_dimension, max_dimension, int(max_dimension*.8),
                         int(max_dimension*.64), int(max_dimension*.48), int(max_dimension*.32))
                for index, dimension in enumerate(sizes):
                    image.thumbnail((dimension, dimension), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    image.save(output, format='WEBP', quality=quality if index == 0 else min(quality, 65),
                               method=4, exif=b'', icc_profile=b'', xmp=b'')
                    content = output.getvalue()
                    if len(content) <= max_bytes:
                        return content
                raise HTTPException(400, 'This image cannot fit the stored photo limit. Resize it and try again.')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(400, 'Invalid image or image is larger than 24 megapixels. Resize it and try again.') from None
