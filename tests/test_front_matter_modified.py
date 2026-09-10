"""Tests for front matter last-modified import (`importModified`).

Runs fully offline with requests_mock — no Trilium server needed.
"""
import json
import os
import tempfile
import unittest

import requests_mock

from trilium_py.client import ETAPI, _format_front_matter_date


class TestFormatFrontMatterDate(unittest.TestCase):
    def test_with_millis(self):
        local, utc = _format_front_matter_date('2025-09-08 12:34:56.789Z')
        self.assertEqual(utc, '2025-09-08 12:34:56.789Z')
        # Same instant, rendered in local time with offset.
        self.assertRegex(local, r'^2025-09-08 \d{2}:34:56\.789[+-]\d{4}$')

    def test_without_millis(self):
        local, utc = _format_front_matter_date('2025-09-01 08:00:00Z')
        self.assertEqual(utc, '2025-09-01 08:00:00.000Z')
        self.assertIn('.000', local)

    def test_rejects_bad_shapes(self):
        self.assertEqual(_format_front_matter_date('yesterday'), (None, None))
        self.assertEqual(_format_front_matter_date('2025-09-08'), (None, None))
        self.assertEqual(_format_front_matter_date(''), (None, None))


class TestUploadMdFileModified(unittest.TestCase):
    NOTE = (
        '---\n'
        'title: Modified note\n'
        'updated: 2025-09-08 12:34:56Z\n'
        'created: 2025-09-01 08:00:00Z\n'
        '---\n'
        '\n'
        'Body text.\n'
    )

    def _write_note(self, body=None):
        tmp = tempfile.NamedTemporaryFile(
            suffix='.md', delete=False, mode='w', encoding='utf-8')
        tmp.write(body or self.NOTE)
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        return tmp.name

    def _upload(self, mock, path, **kwargs):
        created = mock.post('http://bogus:8080/etapi/create-note',
                            json={'note': {'noteId': 'n1'}})
        ea = ETAPI('http://bogus:8080', 'bogus')
        ea.upload_md_file(file=path, parentNoteId='root',
                          parse_math=False, hasFrontMatter=True, **kwargs)
        return json.loads(created.last_request.text)

    def test_modified_sent_when_opted_in(self):
        with requests_mock.Mocker() as mock:
            sent = self._upload(mock, self._write_note(), importModified=True)
        self.assertEqual(sent['utcDateModified'], '2025-09-08 12:34:56.000Z')
        self.assertRegex(sent['dateModified'], r'\.000[+-]\d{4}$')
        # created still flows as before
        self.assertIn('dateCreated', sent)

    def test_modified_omitted_by_default(self):
        with requests_mock.Mocker() as mock:
            sent = self._upload(mock, self._write_note())
        self.assertNotIn('dateModified', sent)
        self.assertNotIn('utcDateModified', sent)
        self.assertIn('dateCreated', sent)

    def test_unparseable_updated_is_omitted(self):
        bad = self.NOTE.replace('updated: 2025-09-08 12:34:56Z', 'updated: someday')
        with requests_mock.Mocker() as mock:
            sent = self._upload(mock, self._write_note(bad), importModified=True)
        self.assertNotIn('dateModified', sent)
        self.assertNotIn('utcDateModified', sent)

    def test_missing_updated_is_omitted(self):
        bare = '---\ntitle: x\ncreated: 2025-09-01 08:00:00Z\n---\n\nBody.\n'
        with requests_mock.Mocker() as mock:
            sent = self._upload(mock, self._write_note(bare), importModified=True)
        self.assertNotIn('dateModified', sent)
        self.assertNotIn('utcDateModified', sent)


if __name__ == '__main__':
    unittest.main()
