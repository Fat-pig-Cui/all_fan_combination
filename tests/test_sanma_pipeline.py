import json
from pathlib import Path
import tempfile
import unittest

from audit_results import audit
from enumerate_combinations import enumerate_sets
from tools.enumerate_sanma import enumerate_sanma


class SanmaPipelineTests(unittest.TestCase):
    def seed(self, root):
        source = root / 'four'
        source.mkdir()
        (source / 'summary.json').write_text(json.dumps({'scope': {'players': 4}, 'combination_count': 1}))
        # Deliberately incorrect old labels must not become sanma exclusions.
        record = {'yaku': ['sanshoku_doujun'], 'mask': 0, 'han': 99,
                  'witness': {'hand': '22446688p22446s', 'win': '6s', 'melds': []}}
        (source / 'combinations.jsonl').write_text(json.dumps(record) + '\n')
        (source / 'rejections.jsonl').write_text('')
        return source

    def test_seed_labels_are_ignored_and_partial_run_is_auditable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.seed(root)
            original = (source / 'combinations.jsonl').read_bytes()
            summary = enumerate_sanma(source, root / 'three', limit=2, timeout_ms=15000)
            self.assertFalse(summary['complete'])
            self.assertEqual(summary['scope']['players'], 3)
            self.assertEqual(summary['combination_count'], 2)
            self.assertEqual(audit(root / 'three')['witnesses_checked'], 2)
            rows = [json.loads(line) for line in (root / 'three/combinations.jsonl').read_text().splitlines()]
            self.assertTrue(all('sanshoku_doujun' not in row['yaku'] and row['han'] != 99 for row in rows))
            self.assertEqual((source / 'combinations.jsonl').read_bytes(), original)

    def test_saved_nuki_certificate_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            enumerate_sanma(self.seed(root), root / 'three', limit=2, timeout_ms=15000)
            path = root / 'three/combinations.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            row = next(r for r in rows if 'north_extraction' in r['condition_certificate'])
            row['condition_certificate']['north_extraction']['uses_just_drawn_tile'] = False
            path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            with self.assertRaisesRegex(ValueError, 'certificate'):
                audit(root / 'three')

    def test_resume_rejects_changed_configuration_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            enumerate_sets(path, players=3, limit=1, timeout_ms=15000)
            summary = json.loads((path / 'summary.json').read_text())
            summary['rules_fingerprint'] = 'wrong'
            (path / 'summary.json').write_text(json.dumps(summary))
            with self.assertRaisesRegex(ValueError, 'Rules differ'):
                enumerate_sets(path, players=3, resume=True)


if __name__ == '__main__':
    unittest.main()
