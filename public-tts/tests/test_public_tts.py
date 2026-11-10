#!/usr/bin/env python3
"""Unit tests for VoiceStudio Speak helpers. No live TTS calls."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import config, cors, languages, queue, rate_limit, wpm
from backend import http_util, jobs, paths, tempo


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




class RatePlanTests(unittest.TestCase):
    def test_slower_uses_atempo(self):
        plan = wpm.plan_rate("one two three four five six seven eight nine ten", 100, baseline_wpm=194)
        self.assertEqual(plan.method, "atempo")
        self.assertEqual(plan.api_speed, 1.0)
        self.assertAlmostEqual(plan.atempo, 100 / 194, places=5)
        self.assertAlmostEqual(plan.expected_duration_s, 6.0, places=3)
        self.assertIn("atempo=", plan.atempo_filter)

    def test_180_also_slower_than_baseline(self):
        plan = wpm.plan_rate("one two three four five six seven eight nine ten", 180, baseline_wpm=194)
        self.assertEqual(plan.method, "atempo")
        self.assertAlmostEqual(plan.atempo, 180 / 194, places=5)
        self.assertAlmostEqual(plan.expected_duration_s, 10 / 180 * 60, places=3)

    def test_faster_uses_native_speed(self):
        plan = wpm.plan_rate("one two three four five six seven eight nine ten", 220, baseline_wpm=194)
        self.assertEqual(plan.method, "native_speed")
        self.assertAlmostEqual(plan.api_speed, 220 / 194, places=5)
        self.assertIsNone(plan.atempo)

    def test_atempo_chain_below_half(self):
        # 80 / 194 ≈ 0.412, needs two stages
        parts = wpm.atempo_chain(80 / 194)
        self.assertGreaterEqual(len(parts), 2)
        product = 1.0
        for part in parts:
            self.assertGreaterEqual(part, 0.5)
            self.assertLessEqual(part, 2.0)
            product *= part
        self.assertAlmostEqual(product, 80 / 194, places=5)


class PathPrefixTests(unittest.TestCase):
    def test_root_api_unchanged(self):
        self.assertEqual(paths.logical_path("/api/jobs"), "/api/jobs")
        self.assertEqual(paths.logical_path("/api/jobs/abc/audio"), "/api/jobs/abc/audio")
        self.assertEqual(paths.logical_path("/"), "/")

    def test_speak_alias(self):
        self.assertEqual(config.PUBLIC_PREFIX, "/speak")
        self.assertEqual(paths.logical_path("/speak"), "/")
        self.assertEqual(paths.logical_path("/speak/"), "/")
        self.assertEqual(paths.logical_path("/speak/api/jobs"), "/api/jobs")
        self.assertEqual(paths.logical_path("/speak/api/jobs/xyz/audio"), "/api/jobs/xyz/audio")
        self.assertEqual(paths.logical_path("/speak/css/styles.css"), "/css/styles.css")


class JobStoreTests(unittest.TestCase):
    def test_queue_position_and_expiry(self):
        store = jobs.JobStore()
        plan = wpm.plan_rate("hello world", 150, baseline_wpm=194)
        first = jobs.Job(job_id="job_one_aaa", text="hello world", language="en",
                         voice_id="narrator", wpm_value=150, plan=plan)
        second = jobs.Job(job_id="job_two_bbb", text="hello world", language="en",
                          voice_id="narrator", wpm_value=150, plan=plan)
        _, pos1 = store.submit(first)
        _, pos2 = store.submit(second)
        self.assertEqual(pos1, 1)
        self.assertEqual(pos2, 2)
        self.assertEqual(store.get("job_two_bbb").status, "queued")
        first.status = "done"
        first.finished_at = 0  # long ago
        first.audio = b"RIFF"
        store.expire()
        self.assertIsNone(store.get("job_one_aaa"))
        self.assertIsNotNone(store.get("job_two_bbb"))

    def test_public_audio_path_is_root_api(self):
        plan = wpm.plan_rate("hello world", 150, baseline_wpm=194)
        job = jobs.Job(job_id="abc123XYZ", text="hello world", language="en",
                       voice_id="narrator", wpm_value=150, plan=plan)
        job.status = "done"
        job.audio = b"x"
        data = job.public_dict()
        self.assertEqual(data["audio_path"], "/api/jobs/abc123XYZ/audio")


class TempoTests(unittest.TestCase):
    def test_stretch_doubles_length(self):
        import io, math, struct, subprocess, wave
        buf = io.BytesIO()
        rate = 8000
        n = rate  # 1 second
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            frames = b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(n))
            wf.writeframes(frames)
        stretched = tempo.stretch(buf.getvalue(), 0.5)
        with wave.open(io.BytesIO(stretched), "rb") as wf:
            duration = wf.getnframes() / float(wf.getframerate())
        self.assertAlmostEqual(duration, 2.0, delta=0.05)


if __name__ == "__main__":
    unittest.main()
