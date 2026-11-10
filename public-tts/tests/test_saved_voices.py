"""Public saved-voice listing exposes only name, slug and language."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import saved


class SavedVoiceListingTests(unittest.TestCase):
    def test_public_list_and_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "amit-agnihotri"
            folder.mkdir()
            (folder / "ref.wav").write_bytes(b"RIFF")
            (folder / "ref.txt").write_text("sample", encoding="utf-8")
            (folder / "meta.json").write_text(json.dumps({
                "slug": "amit-agnihotri",
                "name": "Amit Agnihotri",
                "language": "hi",
                "seed": 42,
            }), encoding="utf-8")
            # Flat profile files must be ignored.
            (root / "demo0001.wav").write_bytes(b"RIFF")
            with mock.patch.dict(os.environ, {"VOICESTUDIO_SAVED_VOICES_DIR": tmp}):
                voices = saved.public_list()
                self.assertEqual(voices, [{
                    "name": "Amit Agnihotri",
                    "slug": "amit-agnihotri",
                    "language": "hi",
                }])
                self.assertTrue(saved.is_known("amit-agnihotri"))
                self.assertTrue(saved.is_known("Amit Agnihotri"))
                self.assertFalse(saved.is_known("narrator"))
                record = saved.get("amit-agnihotri")
                self.assertEqual(record["seed"], 42)
                self.assertNotIn("ref_wav", saved.public_list()[0])


if __name__ == "__main__":
    unittest.main()
