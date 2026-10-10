#!/usr/bin/env python3
"""Create a ZIP snapshot with fixed member metadata and original-content hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from result_records import ARCHIVE_NAME, RECORD_NAMES, verify_archive


def pack(directory: Path):
    sources = {name: (directory / name).read_bytes() for name in RECORD_NAMES}
    temporary = directory / (ARCHIVE_NAME + '.tmp')
    with zipfile.ZipFile(temporary, 'w') as archive:
        for name, data in sources.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    temporary.replace(directory / ARCHIVE_NAME)
    metadata = {
        'schema_version': 1, 'archive': ARCHIVE_NAME,
        'members': {
            name: {'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data),
                   'records': data.count(b'\n') + int(bool(data) and not data.endswith(b'\n'))}
            for name, data in sources.items()
        },
    }
    metadata_path = directory / 'archive.json.tmp'
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    metadata_path.replace(directory / 'archive.json')
    verify_archive(directory)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(pack(args.directory), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
