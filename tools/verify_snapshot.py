#!/usr/bin/env python3
"""Verify published artifacts and core source hashes using only the standard library."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from result_records import verify_archive
from rules import get_rules


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
    result = {'artifacts_checked': len(checked), 'source_hashes_match': True,
              'enumeration_complete': True, 'combination_count': summary['combination_count']}
    archive_path = root / 'results/full/records.zip'
    if archive_path.exists():
        if not {'results/full/records.zip', 'results/full/archive.json'} <= checked:
            raise ValueError('Manifest does not cover the compressed snapshot and its metadata')
        result.update(verify_archive(archive_path.parent))
    profiles = {'4': {'combination_count': summary['combination_count'], 'complete': True}}
    sanma = root / 'results/sanma'
    if sanma.exists():
        required = {('results/sanma/' + name if name != 'REPORT.md' else 'doc/results/sanma/REPORT.md') for name in ('summary.json', 'records.zip', 'archive.json', 'audit.json', 'REPORT.md')}
        if not required <= checked:
            raise ValueError('Manifest does not cover the sanma snapshot')
        data = json.loads((sanma / 'summary.json').read_text(encoding='utf-8'))
        if data['scope']['players'] != 3 or not data['complete'] or data['termination'] != 'unsat':
            raise ValueError('Published sanma snapshot is incomplete or has the wrong player count')
        rules = get_rules(3)
        if data['rules'] != rules.to_dict() or data['rules_fingerprint'] != rules.fingerprint:
            raise ValueError('Sanma rules differ from the published snapshot')
        for name, digest in data['source_sha256'].items():
            path = (root / name).resolve()
            if root not in path.parents or digest_file(path) != digest:
                raise ValueError('Sanma source hash mismatch: ' + name)
        verify_archive(sanma)
        profiles['3'] = {'combination_count': data['combination_count'], 'complete': True}
    result['profiles'] = profiles
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        print(json.dumps(verify(), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
