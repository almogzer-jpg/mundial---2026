"""
שכבת קליטה — מתזמרת את הספקים וכותבת ל-SQLite.

זרימה:
  1. בוחר ספקים פעילים (פתוח + ידני).
  2. ממזג מקורות (הזנה ידנית גוברת על הפתוח עבור תוצאות).
  3. כותב ל-DB בצורה idempotent (בטוח להריץ שוב ושוב).

הוספת ספק API עתידי = הוספתו לרשימת active_providers(), ללא שינוי כאן.
"""
from __future__ import annotations

from data import db
from ingestion.providers.api_football import APIFootballProvider
from ingestion.providers.base import DataProvider, Fixture
from ingestion.providers.manual import ManualProvider
from ingestion.providers.open_data import OpenDataProvider


def active_providers() -> list[DataProvider]:
    """הספקים הפעילים, לפי סדר עדיפות במיזוג (אחרון גובר על תוצאות)."""
    providers: list[DataProvider] = [OpenDataProvider(), ManualProvider()]
    api = APIFootballProvider()
    if api.is_available():           # רק אם מוגדר מפתח ב-.env
        providers.append(api)
    return providers


# --- מיזוג תוצאות מכמה מקורות (מיזוג ברמת שדה) ---
def _merge_fixtures(providers: list[DataProvider]) -> list[Fixture]:
    merged: dict[tuple[str, str], Fixture] = {}
    for provider in providers:
        for fx in provider.get_fixtures():
            key = (fx.home_team, fx.away_team)
            cur = merged.get(key)
            if cur is None:
                merged[key] = fx
                continue
            # תוצאה/סטטוס: ספק מאוחר גובר אם יש לו תוצאה
            if fx.home_score is not None:
                cur.home_score = fx.home_score
                cur.away_score = fx.away_score
                cur.status = fx.status
            # שדות מבניים: ממלאים רק אם חסרים (לא דורסים מבנה תקין)
            cur.group = cur.group or fx.group
            cur.city = cur.city or fx.city
            cur.date_utc = cur.date_utc or fx.date_utc
            if fx.round and fx.round != "Group Stage":
                cur.round = fx.round
    return list(merged.values())


# --- כתיבה ל-DB ---
def ingest_teams(conn, providers: list[DataProvider]) -> int:
    teams = {}
    for provider in providers:
        for t in provider.get_world_cup_teams():
            teams[t.name] = t
    for t in teams.values():
        conn.execute(
            "INSERT INTO teams (name, grp) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET grp = excluded.grp",
            (t.name, t.group),
        )
    return len(teams)


def ingest_historical(conn, providers: list[DataProvider]) -> int:
    rows = []
    for provider in providers:
        for m in provider.get_historical_matches():
            rows.append(
                (m.date, m.home_team, m.away_team, m.home_score,
                 m.away_score, m.tournament, 1 if m.neutral else 0)
            )
    conn.executemany(
        "INSERT OR IGNORE INTO historical_matches "
        "(date, home_team, away_team, home_score, away_score, tournament, neutral) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return conn.execute("SELECT COUNT(*) FROM historical_matches").fetchone()[0]


def ingest_fixtures(conn, providers: list[DataProvider]) -> int:
    name_to_id = {
        row["name"]: row["id"]
        for row in conn.execute("SELECT id, name FROM teams").fetchall()
    }
    fixtures = _merge_fixtures(providers)
    # idempotent: upsert לפי מפתח טבעי -> מזהה המשחק יציב, תחזיות נשמרות
    inserted = 0
    skipped = 0
    for fx in fixtures:
        home_id = name_to_id.get(fx.home_team)
        away_id = name_to_id.get(fx.away_team)
        if home_id is None or away_id is None:
            skipped += 1  # נבחרת שטרם נקבעה (שלב נוקאאוט עתידי)
            continue
        conn.execute(
            "INSERT INTO fixtures "
            "(season, round, grp, date_utc, city, status, "
            " home_team_id, away_team_id, home_goals, away_goals, is_neutral) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(season, home_team_id, away_team_id) DO UPDATE SET "
            " round=excluded.round, grp=COALESCE(excluded.grp, grp), "
            " date_utc=COALESCE(excluded.date_utc, date_utc), "
            " city=COALESCE(excluded.city, city), status=excluded.status, "
            " home_goals=excluded.home_goals, away_goals=excluded.away_goals, "
            " is_neutral=excluded.is_neutral",
            (
                2026, fx.round, fx.group, fx.date_utc, fx.city, fx.status,
                home_id, away_id, fx.home_score, fx.away_score,
                1 if fx.neutral else 0,
            ),
        )
        inserted += 1
    return inserted


def ingest_injuries(conn, providers: list[DataProvider]) -> int:
    """קולט פציעות (מ-API/ידני) -> טבלת injuries. מנקה וכותב מחדש."""
    name_to_id = {
        row["name"]: row["id"]
        for row in conn.execute("SELECT id, name FROM teams").fetchall()
    }
    conn.execute("DELETE FROM injuries")
    n = 0
    for provider in providers:
        for inj in provider.get_injuries():
            team_id = name_to_id.get(inj.get("team"))
            if team_id is None:
                continue
            conn.execute(
                "INSERT INTO injuries (team_id, player_name, type, reason) "
                "VALUES (?, ?, ?, ?)",
                (team_id, inj.get("player"), inj.get("type"), inj.get("reason")),
            )
            n += 1
    return n


def run() -> dict:
    """מריץ קליטה מלאה ומחזיר סיכום."""
    db.init_db()
    providers = active_providers()
    with db.connection() as conn:
        n_teams = ingest_teams(conn, providers)
        n_hist = ingest_historical(conn, providers)
        n_fix = ingest_fixtures(conn, providers)
        n_inj = ingest_injuries(conn, providers)
    return {"teams": n_teams, "historical_matches": n_hist,
            "fixtures": n_fix, "injuries": n_inj}


if __name__ == "__main__":
    summary = run()
    print("קליטה הושלמה:", summary)
