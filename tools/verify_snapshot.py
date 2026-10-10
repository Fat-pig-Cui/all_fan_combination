#!/usr/bin/env python3
"""Verify published artifacts and core source hashes using only the standard library."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify(root: Path = ROOT):
    root = root.resolve()
    checked = set()
    for number, line in enumerate((root / 'results/SHA256SUMS').read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        relative = relative.strip()
        path = (root / relative).resolve()
        if root not in path.parents or relative in checked:
            raise ValueError(f'Manifest line {number}: invalid or duplicate path')
        if digest_file(path) != expected:
            raise ValueError('Artifact hash mismatch: ' + relative)
        checked.add(relative)
    if 'results/full/summary.json' not in checked:
        raise ValueError('Manifest does not include the published summary')
    summary = json.loads((root / 'results/full/summary.json').read_text(encoding='utf-8'))
    if not summary['complete'] or summary['termination'] != 'unsat':
        raise ValueError('Published snapshot is not a complete enumeration')
    for name, expected in summary['source_sha256'].items():
        path = (root / name).resolve()
        if root not in path.parents or digest_file(path) != expected:
            raise ValueError('Core source hash mismatch: ' + name)
    return {'artifacts_checked': len(checked), 'source_hashes_match': True,
            'enumeration_complete': True, 'combination_count': summary['combination_count']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        print(json.dumps(verify(), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
