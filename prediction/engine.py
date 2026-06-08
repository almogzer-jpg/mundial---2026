"""
מנוע התחזית — מרכיב את מודל ה-Poisson מתוך ה-DB ומפיק תחזיות.
"""
from __future__ import annotations

from collections import namedtuple
from datetime import date

import json
from collections import defaultdict

import config
from data import db
from ingestion.providers.manual import OVERRIDES_PATH
from prediction import injuries as inj
from prediction.poisson import PoissonModel, Prediction
from prediction.strength import StrengthModel

Match = namedtuple(
    "Match",
    "date home_team away_team home_score away_score tournament neutral",
)


def load_history(conn) -> list[Match]:
    rows = conn.execute(
        "SELECT date, home_team, away_team, home_score, away_score, "
        "tournament, neutral FROM historical_matches"
    ).fetchall()
    return [Match(*r) for r in rows]


def load_elo(conn) -> dict[str, float]:
    return {
        r["name"]: r["elo"]
        for r in conn.execute("SELECT name, elo FROM teams").fetchall()
        if r["elo"] is not None
    }


def load_injuries(conn) -> dict[str, list[str]]:
    """{team: [player names]} מהפצועים הפעילים."""
    rows = conn.execute(
        "SELECT t.name AS team, i.player_name AS player FROM injuries i "
        "JOIN teams t ON i.team_id = t.id WHERE i.player_name IS NOT NULL"
    ).fetchall()
    by_team = defaultdict(list)
    for r in rows:
        by_team[r["team"]].append(r["player"])
    return by_team


def load_squad_adj(conn) -> dict[str, float]:
    return {r["name"]: (r["squad_adj"] or 0.0)
            for r in conn.execute("SELECT name, squad_adj FROM teams").fetchall()}


def load_motivation() -> dict[str, float]:
    """התאמת מוטיבציה/טקטיקה ידנית (נק' Elo) מקובץ ההזנה הידנית."""
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        return json.loads(OVERRIDES_PATH.read_text(encoding="utf-8")).get("motivation", {})
    except (json.JSONDecodeError, OSError):
        return {}


def build_model(ref_date: date | None = None) -> PoissonModel:
    ref_date = ref_date or date.today()
    with db.connection() as conn:
        history = load_history(conn)
        base_elo = load_elo(conn)
        squad_adj = load_squad_adj(conn)
        injuries_by_team = load_injuries(conn)
    motivation = load_motivation()
    # Final Team Rating = Elo + משקל·כוח-סגל + מוטיבציה
    effective_elo = {
        t: base_elo.get(t, config.ELO_INITIAL)
        + config.CTS_WEIGHT * squad_adj.get(t, 0.0)
        + float(motivation.get(t, 0.0))
        for t in base_elo
    }
    strength = StrengthModel().fit(history, ref_date)
    availability = inj.availability_map(injuries_by_team)
    return PoissonModel(strength, effective_elo, availability=availability)


def predict(model: PoissonModel, home: str, away: str, neutral: bool = True) -> Prediction:
    return model.predict(home, away, neutral)
