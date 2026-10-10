import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from audit_results import audit
from enumerate_combinations import enumerate_sets
from result_records import RECORD_NAMES, iter_record_lines, verify_archive
from tools.pack_results import pack


class ArchiveTests(unittest.TestCase):
    def records(self, directory):
        contents = {
            'combinations.jsonl': '{"役":"平和"}\n{"役":"三暗刻"}\n'.encode('utf-8'),
            'rejections.jsonl': b'{"reason":"not_selected"}',
        }
        for name, data in contents.items():
            (directory / name).write_bytes(data)
        return contents

    def test_original_member_bytes_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            contents = self.records(directory)
            metadata = pack(directory)
            with zipfile.ZipFile(directory / 'records.zip') as archive:
                for name, data in contents.items():
                    self.assertEqual(archive.read(name), data)
            self.assertEqual(metadata['members']['rejections.jsonl']['records'], 1)
            self.assertTrue(verify_archive(directory)['uncompressed_hashes_match'])

    def test_plain_and_archive_readers_produce_identical_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.records(directory)
            original = {name: list(iter_record_lines(directory, name)) for name in RECORD_NAMES}
            pack(directory)
            for name in RECORD_NAMES:
                (directory / name).unlink()
                self.assertEqual(list(iter_record_lines(directory, name)), original[name])

    def test_changed_archive_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            contents = self.records(directory)
            pack(directory)
            with zipfile.ZipFile(directory / 'records.zip', 'w') as archive:
                archive.writestr('combinations.jsonl', b'{"changed":true}\n')
                archive.writestr('rejections.jsonl', contents['rejections.jsonl'])
            with self.assertRaisesRegex(ValueError, 'Uncompressed member mismatch'):
                verify_archive(directory)

    def test_input_timestamps_do_not_change_archive_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.records(directory)
            pack(directory)
            original = (directory / 'records.zip').read_bytes()
            for name in RECORD_NAMES:
                os.utime(directory / name, (1000000000, 1000000000))
            pack(directory)
            self.assertEqual((directory / 'records.zip').read_bytes(), original)

    def test_zip_only_witnesses_recalculate(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            enumerate_sets(directory, limit=3, timeout_ms=15000)
            pack(directory)
            for name in RECORD_NAMES:
                (directory / name).unlink()
            self.assertEqual(audit(directory)['witnesses_checked'], 3)


if __name__ == '__main__':
    unittest.main()
