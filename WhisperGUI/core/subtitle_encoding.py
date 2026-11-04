"""Strict, offline text decoding. Never repair or discard subtitle content."""
import codecs
import re
from dataclasses import dataclass
from pathlib import Path

from charset_normalizer import from_bytes

MAX_FILE_BYTES = 20 * 1024 * 1024
PREVIEW_CHARS = 100_000
SUBTITLE_SUFFIXES = ('.srt', '.ass', '.ssa', '.vtt', '.sbv', '.sub', '.txt')
LEGACY_ENCODINGS = ('cp950', 'big5hkscs', 'gb18030', 'cp932', 'euc_jp', 'cp949',
                    'cp1252', 'cp1250', 'cp1251', 'cp1254', 'cp1256', 'cp874', 'iso8859_1')
ENCODINGS = ('utf-8-sig', 'utf-16-le', 'utf-16-be', 'utf-32-le', 'utf-32-be') + LEGACY_ENCODINGS
BOMS = ((codecs.BOM_UTF32_LE, 'utf-32-le'), (codecs.BOM_UTF32_BE, 'utf-32-be'),
        (codecs.BOM_UTF8, 'utf-8-sig'), (codecs.BOM_UTF16_LE, 'utf-16-le'),
        (codecs.BOM_UTF16_BE, 'utf-16-be'))
CONTROLS = re.compile(r'[\x00-\x08\x0b\x0e-\x1f\x7f-\x9f]')


class EncodingError(ValueError):
    """A localized message key, without subtitle data."""


@dataclass(frozen=True)
class DecodedSubtitle:
    text: str
    encoding: str
    method: str  # bom, utf8, guess, manual

    def utf8(self, with_bom=False):
        # Encode the original decoded string, never the Qt preview (which normalizes newlines).
        return (codecs.BOM_UTF8 if with_bom else b'') + self.text.encode('utf-8', errors='strict')


def read_subtitle(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    check_size(raw)
    return raw


def check_size(raw):
    if len(raw) > MAX_FILE_BYTES:
        raise EncodingError('too_large')
    if not raw:
        raise EncodingError('empty')


def decode_strict(raw, encoding):
    try:
        text = raw.decode('utf-8' if encoding == 'utf-8-sig' else encoding, errors='strict')
    except UnicodeError as error:
        raise EncodingError('decode_error') from error
    if CONTROLS.search(text):
        raise EncodingError('binary')
    return text


def decode_subtitle(raw, encoding='auto'):
    check_size(raw)
    if encoding != 'auto':
        if encoding not in ENCODINGS:
            raise EncodingError('unsupported_encoding')
        # Strip only a matching byte-order mark, not arbitrary leading U+FEFF text.
        payload = raw
        for bom, codec in BOMS:
            if codec == encoding and raw.startswith(bom):
                payload = raw[len(bom):]
                break
        return DecodedSubtitle(decode_strict(payload, encoding), encoding, 'manual')

    # Longest BOM first: UTF-32 LE starts with the UTF-16 LE mark.
    for bom, codec in BOMS:
        if raw.startswith(bom):
            return DecodedSubtitle(decode_strict(raw[len(bom):], codec), codec, 'bom')
    try:
        text = decode_strict(raw, 'utf-8')
        return DecodedSubtitle(text, 'utf-8-sig', 'utf8')
    except EncodingError:
        pass
    if b'\x00' in raw:
        # BOM-less Unicode subtitles normally contain ASCII timecodes and NUL bytes.
        # They remain a guess: users must confirm the preview before saving.
        for codec in ('utf-32-le', 'utf-32-be', 'utf-16-le', 'utf-16-be'):
            try:
                text = decode_strict(raw, codec)
            except EncodingError:
                continue
            if '\n' in text or '\r' in text:
                return DecodedSubtitle(text, codec, 'guess')
        raise EncodingError('binary')
    matches = from_bytes(raw, cp_isolation=list(LEGACY_ENCODINGS),
                         preemptive_behaviour=False, enable_fallback=False)
    for match in matches:
        for codec in LEGACY_ENCODINGS:
            if codecs.lookup(codec).name != codecs.lookup(match.encoding).name:
                continue
            try:
                return DecodedSubtitle(decode_strict(raw, codec), codec, 'guess')
            except EncodingError:
                continue
    raise EncodingError('unknown')


def is_source_destination(source, destination):
    source, destination = Path(source), Path(destination)
    return (destination.resolve() == source.resolve() or
            (source.exists() and destination.exists() and destination.samefile(source)))
