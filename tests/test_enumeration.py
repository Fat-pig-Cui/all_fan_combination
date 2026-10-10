import json
import tempfile
import unittest
from pathlib import Path

from audit_results import audit
from enumerate_combinations import enumerate_sets


class EnumerationTests(unittest.TestCase):
    def test_limit_marks_partial_and_every_witness_recalculates(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            summary = enumerate_sets(directory, limit=12, timeout_ms=15000, log_every=100)
            self.assertFalse(summary['complete'])
            self.assertEqual(summary['termination'], 'combination_limit')
            self.assertEqual(summary['combination_count'], 12)
            self.assertEqual(audit(directory)['witnesses_checked'], 12)

    def test_resume_deduplicates_existing_sets(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            enumerate_sets(directory, limit=5, timeout_ms=15000, log_every=100)
            resumed = enumerate_sets(directory, limit=10, timeout_ms=15000, log_every=100, resume=True)
            self.assertEqual(resumed['combination_count'], 10)
            self.assertTrue(audit(directory)['unique'])

    def test_existing_output_requires_explicit_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            enumerate_sets(directory, limit=1, timeout_ms=15000, log_every=100)
            with self.assertRaises(ValueError):
                enumerate_sets(directory, limit=2, timeout_ms=15000, log_every=100)

    def test_resume_refuses_changed_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            enumerate_sets(directory, limit=1, timeout_ms=15000, log_every=100)
            path = directory / 'summary.json'
            summary = json.loads(path.read_text())
            summary['source_sha256']['calc_fan.py'] = 'changed'
            path.write_text(json.dumps(summary))
            with self.assertRaises(ValueError):
                enumerate_sets(directory, limit=2, timeout_ms=15000, log_every=100, resume=True)


if __name__ == '__main__':
    unittest.main()
