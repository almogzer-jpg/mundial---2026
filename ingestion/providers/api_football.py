"""
ספק API-Football — תוצאות חיות, פציעות וסגלים (אוטומטי).

מממש את אותו ממשק DataProvider כמו המקורות הפתוחים, כך שהוא נכנס
למיזוג ללא שום שינוי במודל/UI/DB. מופעל רק כשמוגדר מפתח ב-.env.
שמות נבחרות מנורמלים לשמות הקנוניים (openfootball) כדי שהמיזוג יעבוד.
"""
from __future__ import annotations

import config
from ingestion.api_football import APIFootballClient, APIFootballError
from ingestion.names import canonical
from ingestion.providers.base import DataProvider, Fixture


class APIFootballProvider(DataProvider):
    name = "api_football"

    def __init__(self):
        self._client = None

    @property
    def client(self) -> APIFootballClient:
        if self._client is None:
            self._client = APIFootballClient()
        return self._client

    def is_available(self) -> bool:
        return bool(config.API_FOOTBALL_KEY)

    # --- תוצאות / לוח חי ---
    def get_fixtures(self) -> list[Fixture]:
        if not self.is_available():
            return []
        try:
            raw = self.client.fixtures()
        except APIFootballError:
            return []
        out: list[Fixture] = []
        for item in raw:
            fx = item.get("fixture", {})
            teams = item.get("teams", {})
            goals = item.get("goals", {})
            league = item.get("league", {})
            status = (fx.get("status") or {}).get("short", "NS")
            home = canonical((teams.get("home") or {}).get("name", ""))
            away = canonical((teams.get("away") or {}).get("name", ""))
            if not home or not away:
                continue
            hg, ag = goals.get("home"), goals.get("away")
            played = status in ("FT", "AET", "PEN")
            out.append(Fixture(
                date_utc=(fx.get("date") or "")[:10],
                home_team=home, away_team=away,
                round=league.get("round", "Group Stage"),
                venue=(fx.get("venue") or {}).get("name"),
                city=(fx.get("venue") or {}).get("city"),
                home_score=hg if played else None,
                away_score=ag if played else None,
                status="FT" if played else status,
                neutral=True,
            ))
        return out

    # --- פציעות ---
    def get_injuries(self) -> list[dict]:
        if not self.is_available():
            return []
        try:
            raw = self.client.injuries()
        except APIFootballError:
            return []
        out = []
        for item in raw:
            player = item.get("player", {})
            team = item.get("team", {})
            out.append({
                "player": player.get("name", ""),
                "team": canonical(team.get("name", "")),
                "type": player.get("type", ""),
                "reason": player.get("reason", ""),
            })
        return out
