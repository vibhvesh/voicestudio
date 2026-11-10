"""Languages the OmniVoice model actually lists in its catalog."""

from __future__ import annotations

import csv
from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def all_languages() -> list[dict]:
    path = config.LANGUAGES_TSV
    if not path.is_file():
        return [{"id": "en", "name": "English", "featured": True}]
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for raw in reader:
            lang_id = (raw.get("language_id") or "").strip()
            name = (raw.get("language_name") or "").strip()
            if not lang_id or not name:
                continue
            rows.append({
                "id": lang_id,
                "name": name,
                "featured": lang_id in config.FEATURED_LANGUAGE_IDS,
            })
    rows.sort(key=lambda r: (not r["featured"], r["name"].lower()))
    return rows


def is_supported(lang_id: str) -> bool:
    wanted = (lang_id or "").strip()
    return any(row["id"] == wanted for row in all_languages())
