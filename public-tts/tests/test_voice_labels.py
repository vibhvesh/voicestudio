"""Short public names for style presets, in a fixed display order."""

from __future__ import annotations

import unittest

from backend import voice_labels


class VoiceLabelTests(unittest.TestCase):
    def test_decorate_uses_short_names_and_order(self):
        raw = [
            {"id": "elderly", "label": "Elderly", "blurb": "Older male, lower pitch"},
            {"id": "narrator", "label": "Narrator (default)", "blurb": "Young adult female, moderate pitch"},
            {"id": "child", "label": "Child", "blurb": "Child voice, higher pitch"},
            {"id": "female_young", "label": "Female, young adult", "blurb": "Clear young adult female voice"},
            {"id": "male_young", "label": "Male, young adult", "blurb": "Clear young adult male voice"},
            {"id": "female_middle", "label": "Female, middle-aged", "blurb": "Middle-aged female voice"},
            {"id": "male_middle", "label": "Male, middle-aged", "blurb": "Middle-aged male, lower pitch"},
            {"id": "whisper", "label": "Whisper", "blurb": "Soft whispered delivery (the only style tag this model accepts)"},
        ]
        decorated = voice_labels.decorate_presets(raw)
        self.assertEqual(
            [(item["id"], item["label"], item["blurb"]) for item in decorated],
            [
                ("narrator", "Priya", "young female"),
                ("female_young", "Anjali", "young female"),
                ("male_young", "Rohan", "young male"),
                ("female_middle", "Sunita", "middle-aged female"),
                ("male_middle", "Vikram", "middle-aged male"),
                ("child", "Chintu", "child"),
                ("elderly", "Dadaji", "elderly"),
                ("whisper", "Whisper", "soft whisper"),
            ],
        )

    def test_language_hint(self):
        self.assertEqual(voice_labels.language_hint("hi"), "Hindi")
        self.assertEqual(voice_labels.language_hint(""), "saved voice")


if __name__ == "__main__":
    unittest.main()
