import json
import tempfile
import unittest
from pathlib import Path

from audit_results import audit
from calc_fan import BIT, Context, parse_tiles, score_hand
from enumerate_combinations import combination_record
from reachability import condition_certificate
from shape_solver import Witness
from tools.revalidate_snapshot import revalidate


class RevalidationTests(unittest.TestCase):
    def test_invalid_old_combination_is_rejected_and_valid_seed_is_recalculated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / 'source', root / 'output'
            source.mkdir()
            witness = Witness(parse_tiles('23m 456p 789s 456s 88p'), (), Context(0), True, BIT['pinfu'])
            score = score_hand(witness.hand, witness.context)[0]
            good = combination_record(witness, score, condition_certificate(witness))
            bad = {'yaku': ['chankan', 'double_riichi'], 'witness': {
                'hand': '12m 123p 123s 456s 77p', 'win': '3m', 'riichi': 2,
                'event': 'chankan', 'melds': []}}
            (source / 'summary.json').write_text(json.dumps({'combination_count': 2}))
            (source / 'combinations.jsonl').write_text(json.dumps(bad) + '\n' + json.dumps(good) + '\n')
            (source / 'rejections.jsonl').write_text('')
            summary = revalidate(source, output, limit=1)
            self.assertFalse(summary['complete'])
            self.assertEqual(summary['revalidation']['removed_source_combinations'], 1)
            rejected = json.loads((output / 'rejections.jsonl').read_text())
            self.assertEqual(rejected['reason'], 'double_riichi_kakan_furiten')
            self.assertEqual(audit(output)['witnesses_checked'], 1)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'new output directory'):
                revalidate(root, root)


if __name__ == '__main__':
    unittest.main()
