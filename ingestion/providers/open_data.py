"""
ספק נתונים פתוחים — חינמי לחלוטין, ללא הרשמה וללא מפתח.

מקורות:
  • martj42/international_results  → תוצאות היסטוריות + לוח מונדיאל 2026
  • openfootball/world-cup         → שיוך 12 הבתים (A-L) לנבחרות

מוריד פעם ביום ושומר עותק מקומי (cache) לעבודה גם offline.
"""
from __future__ import annotations

import csv
import io
import re
import time
from pathlib import Path

import requests

import config
from ingestion.names import canonical
from ingestion.providers.base import (
    DataProvider,
    Fixture,
    HistoricalMatch,
    WorldCupTeam,
)

RESULTS_URL = (
    "https://raw.githubusercontent.com/martj42/"
    "international_results/master/results.csv"
)
CUP_URL = (
    "https://raw.githubusercontent.com/openfootball/"
    "world-cup/master/2026--usa/cup.txt"
)

WORLD_CUP_TOURNAMENT = "FIFA World Cup"
WORLD_CUP_YEAR = "2026"


class OpenDataProvider(DataProvider):
    name = "open_data"

    def __init__(self, cache_ttl: int = 86400):
        self.cache_ttl = cache_ttl  # שניות (ברירת מחדל: יום)

    # --- הורדה עם cache ---
    def _download(self, url: str, filename: str) -> str:
        path = config.CACHE_DIR / filename
        fresh = (
            path.exists()
            and time.time() - path.stat().st_mtime < self.cache_ttl
        )
        if fresh:
            return path.read_text(encoding="utf-8")

        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        text = resp.text
        path.write_text(text, encoding="utf-8")
        return text

    def is_available(self) -> bool:
        try:
            requests.head(RESULTS_URL, timeout=10)
            return True
        except requests.RequestException:
            return False

    # --- תוצאות היסטוריות (רק משחקים שהושלמו) ---
    def get_historical_matches(self) -> list[HistoricalMatch]:
        text = self._download(RESULTS_URL, "international_results.csv")
        reader = csv.DictReader(io.StringIO(text))
        matches: list[HistoricalMatch] = []
        for row in reader:
            hs, aws = row.get("home_score"), row.get("away_score")
            if not _is_int(hs) or not _is_int(aws):
                continue  # משחק עתידי / ללא תוצאה
            matches.append(
                HistoricalMatch(
                    date=row["date"],
                    home_team=canonical(row["home_team"]),
                    away_team=canonical(row["away_team"]),
                    home_score=int(hs),
                    away_score=int(aws),
                    tournament=row.get("tournament", "").strip(),
                    neutral=_is_true(row.get("neutral")),
                )
            )
        return matches

    # --- לוח מונדיאל 2026 (משחקי שלב הבתים) ---
    def get_fixtures(self) -> list[Fixture]:
        text = self._download(RESULTS_URL, "international_results.csv")
        reader = csv.DictReader(io.StringIO(text))
        groups = self._team_to_group()
        fixtures: list[Fixture] = []
        for row in reader:
            if row.get("tournament", "").strip() != WORLD_CUP_TOURNAMENT:
                continue
            if not row.get("date", "").startswith(WORLD_CUP_YEAR):
                continue
            home = canonical(row["home_team"])
            away = canonical(row["away_team"])
            hs, aws = row.get("home_score"), row.get("away_score")
            played = _is_int(hs) and _is_int(aws)
            # שיוך לבית: אם שתי הנבחרות באותו בית -> שלב בתים
            grp = groups.get(home) if groups.get(home) == groups.get(away) else None
            fixtures.append(
                Fixture(
                    date_utc=row["date"],
                    home_team=home,
                    away_team=away,
                    round="Group Stage" if grp else "Knockout",
                    group=grp,
                    city=row.get("city", "").strip() or None,
                    home_score=int(hs) if played else None,
                    away_score=int(aws) if played else None,
                    status="FT" if played else "NS",
                    neutral=_is_true(row.get("neutral")),
                )
            )
        return fixtures

    # --- 48 הנבחרות + הבתים שלהן ---
    def get_world_cup_teams(self) -> list[WorldCupTeam]:
        mapping = self._team_to_group()
        return [WorldCupTeam(name=t, group=g) for t, g in mapping.items()]

    # --- עזר: ניתוח שורות הבתים מ-openfootball ---
    def _team_to_group(self) -> dict[str, str]:
        text = self._download(CUP_URL, "wc2026_cup.txt")
        mapping: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            m = re.match(r"^Group\s+([A-L])\s*\|\s*(.+)$", line)
            if not m:
                continue
            group_letter = m.group(1)
            # שמות מופרדים ב-2+ רווחים (שם נבחרת עשוי להכיל רווח בודד)
            teams = [t.strip() for t in re.split(r"\s{2,}", m.group(2)) if t.strip()]
            for team in teams:
                mapping[team] = group_letter
        return mapping


def _is_int(value) -> bool:
    if value is None:
        return False
    value = str(value).strip()
    return bool(re.fullmatch(r"-?\d+", value))


def _is_true(value) -> bool:
    return str(value).strip().upper() in {"TRUE", "1", "YES"}
