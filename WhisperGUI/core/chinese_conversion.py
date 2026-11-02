"""Offline Chinese script conversion; no settings, network or source-file writes."""
from functools import lru_cache
from pathlib import Path

MAX_TEXT_CHARS = 500_000
MAX_FILE_BYTES = 2 * 1024 * 1024
DIRECTIONS = ('t2s', 's2t')


class ConversionError(ValueError):
    pass


@lru_cache(maxsize=2)
def _converter(direction):
    try:
        from opencc import OpenCC
    except ImportError:
        raise ConversionError('missing_dependency') from None
    return OpenCC(direction)


def convert_text(text, direction):
    if direction not in DIRECTIONS:
        raise ConversionError('direction_error')
    if len(text) > MAX_TEXT_CHARS:
        raise ConversionError('too_large')
    # OpenCC preserves whitespace, numbers and SRT timecodes. Use the standard
    # scripts, without regional vocabulary substitution (s2twp/tw2sp).
    return _converter(direction).convert(text)


def read_text_file(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ConversionError('too_large')
    encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    try:
        text = raw.decode(encoding)
    except UnicodeError:
        raise ConversionError('encoding_error') from None
    if '\x00' in text:
        raise ConversionError('encoding_error')
    if len(text) > MAX_TEXT_CHARS:
        raise ConversionError('too_large')
    return text
