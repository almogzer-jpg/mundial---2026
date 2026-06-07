"""
שכבת שירותים לדשבורד — עוטפת את המודל, הטבלאות והסימולציה
בפונקציות נוחות + cache, כדי שה-UI יישאר נקי ומהיר.
"""
from __future__ import annotations

from datetime import date

import config
from data import db
from prediction import engine
from prediction.poisson import Prediction
from prediction import scorers
from tournament import bracket, projection, simulate
from tournament.standings import compute_all


def fmt_date(iso: str) -> str:
    """ISO -> DD/MM/YYYY (תקן ישראלי)."""
    try:
        y, m, d = iso.split("-")
        return f"{d}/{m}/{y}"
    except (ValueError, AttributeError):
        return iso or ""


# --- נתונים בסיסיים ---
def load_fixtures(season: int = 2026) -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT f.id, f.date_utc, f.grp, f.round, f.status, f.city, "
            "f.is_neutral, f.home_goals, f.away_goals, "
            "h.name AS home, a.name AS away, h.elo AS home_elo, a.elo AS away_elo "
            "FROM fixtures f "
            "JOIN teams h ON f.home_team_id = h.id "
            "JOIN teams a ON f.away_team_id = a.id "
            "ORDER BY f.date_utc, f.id"
        ).fetchall()
    return [dict(r) for r in rows]


def load_teams() -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT name, grp, elo FROM teams ORDER BY elo DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def team_groups() -> dict[str, str]:
    with db.connection() as conn:
        return {
            r["name"]: r["grp"]
            for r in conn.execute(
                "SELECT name, grp FROM teams WHERE grp IS NOT NULL"
            ).fetchall()
        }


def api_connected() -> bool:
    """האם ספק ה-API-Football פעיל (מוגדר מפתח)."""
    return bool(config.API_FOOTBALL_KEY)


def injuries_by_team() -> dict[str, list[str]]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT t.name AS team, i.player_name AS player FROM injuries i "
            "JOIN teams t ON i.team_id = t.id WHERE i.player_name IS NOT NULL"
        ).fetchall()
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r["team"], []).append(r["player"])
    return out


def elo_history(team: str) -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT eh.date, eh.rating FROM elo_history eh "
            "JOIN teams t ON eh.team_id = t.id WHERE t.name = ? ORDER BY eh.date",
            (team,),
        ).fetchall()
    return [dict(r) for r in rows]


# --- חיזוי ---
def build_model():
    return engine.build_model(date.today())


def predict(model, home: str, away: str, neutral: bool = True) -> Prediction:
    return model.predict(home, away, neutral)


# --- טבלאות בתים ---
def standings():
    with db.connection() as conn:
        from tournament.standings import results_from_db
        results = results_from_db(conn)
    return compute_all(results, team_groups())


# --- סימולציה ---
def simulate_tournament(model, n_runs: int = config.__dict__.get("MONTE_CARLO_RUNS", 5000)):
    with db.connection() as conn:
        fixtures = simulate.group_fixtures_from_db(conn)
    probs = simulate.simulate(model, fixtures, team_groups(), n_runs=n_runs)
    played = sum(1 for f in fixtures if f["played"])
    return probs, played, len(fixtures)


def golden_boot(sim_probs: dict) -> list[dict]:
    """תחזית מלך שערים מתוך פלט הסימולציה."""
    return scorers.golden_boot(sim_probs)


def projected_bracket(model):
    """בראקט נוקאאוט חזוי (rounds, champion)."""
    with db.connection() as conn:
        fixtures = simulate.group_fixtures_from_db(conn)
    return projection.projected_bracket(model, fixtures, team_groups())


# --- דיוק המודל (תחזיות שמורות מול תוצאות) ---
def saved_predictions_vs_actual() -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT p.fixture_id, p.p_home, p.p_draw, p.p_away, p.likely_score, "
            "p.confidence, f.home_goals, f.away_goals, "
            "h.name AS home, a.name AS away, f.date_utc "
            "FROM predictions p JOIN fixtures f ON p.fixture_id = f.id "
            "JOIN teams h ON f.home_team_id = h.id "
            "JOIN teams a ON f.away_team_id = a.id "
            "WHERE f.home_goals IS NOT NULL ORDER BY f.date_utc"
        ).fetchall()
    return [dict(r) for r in rows]
