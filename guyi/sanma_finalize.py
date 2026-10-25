#!/usr/bin/env python3
"""Run the full corrected sanma model, then audit and publish its delta."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'ordinary'


def main():
    command = [sys.executable, str(ROOT / 'enumerate_sanma_delta.py'),
               '--mode', 'ancient', '--output-root', str(OUTPUT)]
    if (OUTPUT / 'results_sanma_ancient' / 'summary.json').exists():
        command.append('--resume')
    for path in [ROOT / 'ordinary' / 'sanma_ranked_baseline']:
        if not path.exists():
            continue
        command.extend(['--seed', str(path)])
    subprocess.run(command, cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / 'sanma_delta_report.py')], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
