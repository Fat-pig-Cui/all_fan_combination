import copy
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tools.analyze_yakuman import main, report
from tools.verify_yakuman import ROOT, verify


class YakumanResultTests(unittest.TestCase):
    def profile(self, players):
        payload = json.loads((ROOT / 'results/yakuman/summary.json').read_text(encoding='utf-8'))
        profile = copy.deepcopy(payload['profiles'][str(players)])
        profile['combinations'] = profile['combinations'][:1]
        profile['combination_count'] = 1
        profile['multipliers'] = {str(profile['combinations'][0]['multiple']): 1}
        return profile

    def generate(self, directory, players):
        with patch('sys.argv', ['analyze_yakuman', '--players', str(players), '--output', str(directory)]), \
                patch('tools.analyze_yakuman.profile', return_value=self.profile(players)), \
                redirect_stdout(StringIO()):
            main()

    def test_single_profile_outputs_only_requested_players(self):
        for players in (3, 4):
            with self.subTest(players=players), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                self.generate(directory, players)
                payload = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))
                self.assertEqual(set(payload['profiles']), {str(players)})
                record = json.loads((directory / 'witnesses.jsonl').read_text(encoding='utf-8'))
                self.assertEqual(record['players'], players)
                self.assertEqual(verify(directory)['witnesses_checked'], 1)
                text = (directory / 'REPORT.md').read_text(encoding='utf-8')
                self.assertIn('| 四麻 |' if players == 4 else '| 三麻 |', text)
                self.assertNotIn('| 三麻 |' if players == 4 else '| 四麻 |', text)

    def test_changed_witness_export_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.generate(directory, 4)
            (directory / 'witnesses.jsonl').write_text('', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'witness export mismatch'):
                verify(directory)

    def test_changed_multiplier_distribution_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.generate(directory, 3)
            path = directory / 'summary.json'
            payload = json.loads(path.read_text(encoding='utf-8'))
            payload['profiles']['3']['multipliers'] = {'1': 2}
            path.write_text(json.dumps(payload), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'multiplier distribution mismatch'):
                verify(directory)

    def test_report_preserves_markdown_table(self):
        text = report({'4': self.profile(4), '3': self.profile(3)})
        self.assertIn('|---|---:|---|\n| 四麻 | 1 | 1倍:1 |\n| 三麻 | 1 | 1倍:1 |\n', text)


if __name__ == '__main__':
    unittest.main()
