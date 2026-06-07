"""
לקוח API-Football.
כל קריאה עוברת דרך מגביל הקצב + שכבת cache (קבצי JSON עם TTL),
ונרשמת ב-ingestion_log. מוכן לפעולה ברגע שמוזן מפתח ב-.env.

מקור התיעוד: https://www.api-football.com/documentation-v3
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

import config
from data import db
from ingestion.rate_limiter import RateLimiter


class APIFootballError(RuntimeError):
    pass


class APIFootballClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.API_FOOTBALL_KEY
        self.base_url = config.API_BASE_URL
        self.limiter = RateLimiter()
        self.session = requests.Session()
        self.session.headers.update(
            {config.API_AUTH_HEADER: self.api_key, **config.API_EXTRA_HEADERS}
        )

    # --- ליבה ---
    def _cache_path(self, endpoint: str, params: dict) -> Path:
        key = f"{endpoint}?{json.dumps(params, sort_keys=True)}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        safe = endpoint.strip("/").replace("/", "_")
        return config.CACHE_DIR / f"{safe}_{digest}.json"

    def _read_cache(self, path: Path, ttl_seconds: int) -> dict | None:
        if not path.exists():
            return None
        if ttl_seconds >= 0 and time.time() - path.stat().st_mtime > ttl_seconds:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _log(self, endpoint: str, params: dict, status: str, rows: int) -> None:
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO ingestion_log (endpoint, params, fetched_at, status, rows)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    endpoint,
                    json.dumps(params, sort_keys=True),
                    datetime.now(timezone.utc).isoformat(),
                    status,
                    rows,
                ),
            )

    def get(
        self,
        endpoint: str,
        params: dict | None = None,
        ttl_seconds: int = 3600,
        max_retries: int = 3,
    ) -> list[dict[str, Any]]:
        """
        מבצע GET ל-endpoint ומחזיר את רשימת ה-'response'.
        ttl_seconds: כמה זמן ה-cache תקף (0 = ללא cache, -1 = תמיד מה-cache אם קיים).
        """
        params = params or {}
        cache_path = self._cache_path(endpoint, params)

        cached = self._read_cache(cache_path, ttl_seconds) if ttl_seconds != 0 else None
        if cached is not None:
            return cached.get("response", [])

        if not self.api_key:
            raise APIFootballError(
                "לא הוגדר מפתח API. הוסף API_FOOTBALL_KEY לקובץ .env"
            )

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        backoff = 2.0
        for attempt in range(1, max_retries + 1):
            self.limiter.acquire()
            try:
                resp = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                if attempt == max_retries:
                    self._log(endpoint, params, f"error:{exc}", 0)
                    raise APIFootballError(f"שגיאת רשת: {exc}") from exc
                time.sleep(backoff)
                backoff *= 2
                continue

            if resp.status_code == 429:  # rate limit מהשרת
                time.sleep(backoff)
                backoff *= 2
                continue
            if resp.status_code != 200:
                self._log(endpoint, params, f"http:{resp.status_code}", 0)
                raise APIFootballError(f"HTTP {resp.status_code}: {resp.text[:200]}")

            payload = resp.json()
            # API-Football מחזיר שגיאות לוגיות בשדה 'errors'
            errors = payload.get("errors")
            if errors:
                self._log(endpoint, params, f"api_error:{errors}", 0)
                raise APIFootballError(f"שגיאת API: {errors}")

            response = payload.get("response", [])
            cache_path.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            self._log(endpoint, params, "ok", len(response))
            return response

        self._log(endpoint, params, "exhausted_retries", 0)
        raise APIFootballError("נכשל לאחר מספר ניסיונות (rate limit מתמשך?)")

    # --- קריאות נוחות לטורניר ---
    def status(self) -> list[dict]:
        """מצב החשבון והמכסה - שימושי לבדיקת חיבור."""
        return self.get("status", ttl_seconds=0)

    def fixtures(self) -> list[dict]:
        return self.get(
            "fixtures",
            {"league": config.WORLD_CUP_LEAGUE_ID, "season": config.SEASON},
        )

    def standings(self) -> list[dict]:
        return self.get(
            "standings",
            {"league": config.WORLD_CUP_LEAGUE_ID, "season": config.SEASON},
        )

    def squad(self, team_id: int) -> list[dict]:
        return self.get("players/squads", {"team": team_id}, ttl_seconds=86400)

    def injuries(self) -> list[dict]:
        return self.get(
            "injuries",
            {"league": config.WORLD_CUP_LEAGUE_ID, "season": config.SEASON},
        )

    def lineups(self, fixture_id: int) -> list[dict]:
        return self.get("fixtures/lineups", {"fixture": fixture_id})

    def events(self, fixture_id: int) -> list[dict]:
        return self.get("fixtures/events", {"fixture": fixture_id})


if __name__ == "__main__":
    # בדיקת חיבור מהירה (דורש מפתח ב-.env)
    db.init_db()
    client = APIFootballClient()
    info = client.status()
    print(json.dumps(info, ensure_ascii=False, indent=2))
