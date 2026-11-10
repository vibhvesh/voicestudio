#!/usr/bin/env python3
"""Unit tests for VoiceStudio Speak helpers. No live TTS calls."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import config, cors, languages, queue, rate_limit, wpm
from backend import http_util


class WpmTests(unittest.TestCase):
    def test_space_delimited_count(self):
        self.assertEqual(wpm.word_count("one two three four five"), 5)

    def test_cjk_count(self):
        self.assertGreaterEqual(wpm.word_count("你好世界朋友们"), 7)

    def test_duration_formula(self):
        duration, words, capped = wpm.duration_from_wpm("one two three four five", 150)
        self.assertEqual(words, 5)
        self.assertAlmostEqual(duration, 2.0, places=3)
        self.assertFalse(capped)

    def test_duration_scales_with_wpm(self):
        slow, _, _ = wpm.duration_from_wpm("one two three four five six", 80)
        fast, _, _ = wpm.duration_from_wpm("one two three four five six", 200)
        self.assertGreater(slow, fast)
        self.assertAlmostEqual(slow, 6 / 80 * 60, places=3)

    def test_duration_cap(self):
        text = " ".join(["word"] * 200)
        duration, words, capped = wpm.duration_from_wpm(text, 80, min_s=1, max_s=45)
        self.assertEqual(words, 200)
        self.assertEqual(duration, 45)
        self.assertTrue(capped)


class LanguageTests(unittest.TestCase):
    def test_catalog_includes_english_and_hindi(self):
        ids = {row["id"] for row in languages.all_languages()}
        self.assertIn("en", ids)
        self.assertIn("hi", ids)
        self.assertGreater(len(ids), 100)
        self.assertTrue(languages.is_supported("hi"))
        self.assertFalse(languages.is_supported("not-a-lang"))


class CorsTests(unittest.TestCase):
    def test_bowlinger_https_allowed(self):
        self.assertEqual(cors.allow_origin("https://bowlinger.net"), "https://bowlinger.net")
        headers = dict(cors.headers_for("https://bowlinger.net"))
        self.assertEqual(headers["Access-Control-Allow-Origin"], "https://bowlinger.net")

    def test_unknown_origin_not_echoed(self):
        self.assertIsNone(cors.allow_origin("https://evil.example"))
        headers = dict(cors.headers_for("https://evil.example"))
        self.assertNotIn("Access-Control-Allow-Origin", headers)


class QueueAndLimitTests(unittest.TestCase):
    def test_single_job_lock(self):
        self.assertTrue(queue.try_acquire())
        self.assertFalse(queue.try_acquire())
        queue.release()
        self.assertTrue(queue.try_acquire())
        queue.release()

    def test_rate_limit_and_forwarded_ip(self):
        ip = "203.0.113.50"
        # isolate by using a fresh ip
        for _ in range(config.RATE_LIMIT_PER_HOUR):
            ok, _, _, _ = rate_limit.check(ip)
            self.assertTrue(ok)
            rate_limit.commit(ip)
        ok, reason, retry, remaining = rate_limit.check(ip)
        self.assertFalse(ok)
        self.assertEqual(remaining, 0)
        self.assertGreater(retry, 0)
        self.assertIn("hourly limit", reason)
        forwarded = rate_limit.client_ip({"X-Forwarded-For": "198.51.100.9, 10.0.0.1"}, "127.0.0.1")
        self.assertEqual(forwarded, "198.51.100.9")
        cf = rate_limit.client_ip({"CF-Connecting-IP": "198.51.100.10"}, "10.0.0.2")
        self.assertEqual(cf, "198.51.100.10")


class MultipartTests(unittest.TestCase):
    def test_parse_fields_and_file(self):
        body = (
            b"------X\r\n"
            b'Content-Disposition: form-data; name="text"\r\n\r\nhello world\r\n'
            b"------X\r\n"
            b'Content-Disposition: form-data; name="reference"; filename="voice.wav"\r\n'
            b"Content-Type: audio/wav\r\n\r\nRIFFDATA\r\n"
            b"------X--\r\n"
        )
        fields, upload = http_util.parse_multipart(body, "multipart/form-data; boundary=----X")
        self.assertEqual(fields["text"], "hello world")
        self.assertEqual(upload[0], "voice.wav")
        self.assertEqual(upload[1], b"RIFFDATA")


class StaticPathTests(unittest.TestCase):
    def test_index_and_traversal(self):
        root = ROOT / "frontend"
        self.assertEqual(http_util.safe_static(root, "/").name, "index.html")
        self.assertEqual(http_util.safe_static(root, "/css/styles.css").name, "styles.css")
        self.assertIsNone(http_util.safe_static(root, "/../../etc/passwd"))


if __name__ == "__main__":
    unittest.main()
