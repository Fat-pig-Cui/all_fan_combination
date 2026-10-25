"""Read local JSONL runs or the losslessly compressed published snapshot."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

ARCHIVE_NAME = 'records.zip'
RECORD_NAMES = ('combinations.jsonl', 'rejections.jsonl')


def iter_record_lines(directory: Path, name: str):
    if name not in RECORD_NAMES:
        raise ValueError('Unknown record file: ' + name)
    plain = directory / name
    if plain.is_file():
        with plain.open(encoding='utf-8') as handle:
            yield from handle
        return
    with zipfile.ZipFile(directory / ARCHIVE_NAME) as archive:
        with archive.open(name) as binary:
            with io.TextIOWrapper(binary, encoding='utf-8') as handle:
                yield from handle


def verify_archive(directory: Path):
    metadata = json.loads((directory / 'archive.json').read_text(encoding='utf-8'))
    if metadata['schema_version'] != 1 or metadata['archive'] != ARCHIVE_NAME:
        raise ValueError('Unsupported archive metadata')
    members = metadata['members']
    if set(members) != set(RECORD_NAMES):
        raise ValueError('Archive metadata must describe both record files')
    with zipfile.ZipFile(directory / ARCHIVE_NAME) as archive:
        if sorted(archive.namelist()) != sorted(RECORD_NAMES):
            raise ValueError('Unexpected or duplicate ZIP members')
        for name, expected in members.items():
            digest = hashlib.sha256()
            size = 0
            lines = 0
            last = b''
            with archive.open(name) as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(chunk)
                    size += len(chunk)
                    lines += chunk.count(b'\n')
                    last = chunk[-1:]
            lines += int(bool(last) and last != b'\n')
            if (digest.hexdigest() != expected['sha256'] or size != expected['size_bytes']
                    or lines != expected['records']):
                raise ValueError('Uncompressed member mismatch: ' + name)
    return {'archive_members_checked': len(members), 'uncompressed_hashes_match': True}
