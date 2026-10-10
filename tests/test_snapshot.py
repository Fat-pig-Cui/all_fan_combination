import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_snapshot import verify


class SnapshotTests(unittest.TestCase):
    def snapshot(self, root):
        (root / 'results/full').mkdir(parents=True)
        source = root / 'calc_fan.py'
        source.write_text('# baseline source\n', encoding='utf-8')
        summary = root / 'results/full/summary.json'
        summary.write_text(json.dumps({
            'complete': True, 'termination': 'unsat', 'combination_count': 1,
            'source_sha256': {'calc_fan.py': hashlib.sha256(source.read_bytes()).hexdigest()},
        }), encoding='utf-8')
        manifest = root / 'results/SHA256SUMS'
        manifest.write_text(hashlib.sha256(summary.read_bytes()).hexdigest() +
                            '  results/full/summary.json\n', encoding='utf-8')
        return summary, source

    def test_matching_snapshot_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.snapshot(root)
            self.assertEqual(verify(root)['combination_count'], 1)

    def test_changed_result_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary, _ = self.snapshot(root)
            summary.write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Artifact hash mismatch'):
                verify(root)

    def test_changed_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, source = self.snapshot(root)
            source.write_text('# changed source\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Core source hash mismatch'):
                verify(root)


if __name__ == '__main__':
    unittest.main()
