"""
ספק הזנה ידנית — גיבוי תמידי לכל מה שחסר במקורות הפתוחים
ולעדכון תוצאות חיות במהלך הטורניר.

קורא מקובץ JSON ידני (data/manual/overrides.json) אם קיים.
המבנה גמיש; כרגע תומך בעדכון תוצאות משחקים (results).
ה-UI (שלב 5) יכתוב לקובץ זה דרך טופס.
"""
from __future__ import annotations

import json
from pathlib import Path

import config
from ingestion.providers.base import DataProvider, Fixture

MANUAL_DIR = config.DATA_DIR / "manual"
OVERRIDES_PATH = MANUAL_DIR / "overrides.json"


class ManualProvider(DataProvider):
    name = "manual"

    def __init__(self):
        MANUAL_DIR.mkdir(exist_ok=True)

    def _load(self) -> dict:
        if not OVERRIDES_PATH.exists():
            return {}
        try:
            return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def get_fixtures(self) -> list[Fixture]:
        """תוצאות/משחקים שהוזנו ידנית (גוברים על המקור הפתוח במיזוג)."""
        data = self._load()
        fixtures: list[Fixture] = []
        for r in data.get("results", []):
            # תומך בשני האיותים: home/away (מהדשבורד) או home_team/away_team
            home = r.get("home") or r.get("home_team")
            away = r.get("away") or r.get("away_team")
            fixtures.append(
                Fixture(
                    date_utc=r.get("date", ""),
                    home_team=home,
                    away_team=away,
                    round=r.get("round", "Group Stage"),
                    group=r.get("group"),
                    home_score=r.get("home_score"),
                    away_score=r.get("away_score"),
                    status="FT" if r.get("home_score") is not None else "NS",
                    neutral=r.get("neutral", True),
                )
            )
        return fixtures

    def get_injuries(self) -> list[dict]:
        return self._load().get("injuries", [])

    def get_squads(self, team_name: str) -> list[dict]:
        squads = self._load().get("squads", {})
        return squads.get(team_name, [])
