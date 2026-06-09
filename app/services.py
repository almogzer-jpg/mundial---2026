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
            "SELECT name, grp, elo, ssi, squad_adj, squad_n FROM teams ORDER BY elo DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def team_info(name: str) -> dict:
    with db.connection() as conn:
        r = conn.execute(
            "SELECT name, grp, elo, ssi, squad_adj, squad_n FROM teams WHERE name = ?",
            (name,),
        ).fetchone()
    return dict(r) if r else {}


def squad(name: str) -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT sp.name, sp.pos, sp.age, sp.caps, sp.goals, sp.club, sp.clubnat, sp.rating "
            "FROM squad_players sp JOIN teams t ON sp.team_id = t.id "
            "WHERE t.name = ? ORDER BY sp.caps DESC",
            (name,),
        ).fetchall()
    return [dict(r) for r in rows]


def confidence_level(home: str, away: str) -> str:
    """'strong' אם לשתי הנבחרות יש נתוני סגל, אחרת 'partial'."""
    ti, ta = team_info(home), team_info(away)
    n_h, n_a = (ti.get("squad_n") or 0), (ta.get("squad_n") or 0)
    return "strong" if (n_h >= 15 and n_a >= 15) else "partial"


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


def h2h_matches(home: str, away: str) -> list[dict]:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT home_team, away_team, home_score, away_score FROM historical_matches "
            "WHERE (home_team=? AND away_team=?) OR (home_team=? AND away_team=?) "
            "ORDER BY date DESC LIMIT 20",
            (home, away, away, home),
        ).fetchall()
    return [{"home": r["home_team"], "away": r["away_team"],
             "hs": r["home_score"], "as": r["away_score"]} for r in rows]


def recent_form(team: str, n: int = 5) -> list[dict]:
    """N המשחקים האחרונים של הנבחרת (מנקודת מבטה)."""
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT date, home_team, away_team, home_score, away_score "
            "FROM historical_matches WHERE home_team=? OR away_team=? "
            "ORDER BY date DESC LIMIT ?", (team, team, n),
        ).fetchall()
    out = []
    for r in rows:
        if r["home_team"] == team:
            gf, ga, opp = r["home_score"], r["away_score"], r["away_team"]
        else:
            gf, ga, opp = r["away_score"], r["home_score"], r["home_team"]
        res = "W" if gf > ga else "L" if gf < ga else "D"
        out.append({"date": r["date"], "opp": opp, "gf": gf, "ga": ga, "res": res})
    return out


def h2h_record(home: str, away: str) -> dict:
    matches = h2h_matches(home, away)
    hw = d = aw = 0
    for m in matches:
        if m["hs"] == m["as"]:
            d += 1
        else:
            winner = m["home"] if m["hs"] > m["as"] else m["away"]
            hw += (winner == home)
            aw += (winner == away)
    return {"home_wins": hw, "draws": d, "away_wins": aw,
            "n": len(matches), "recent": matches[:6]}


def top_scorers_of(team: str, n: int = 3) -> list[dict]:
    scorers = [p for p in squad(team) if (p.get("goals") or 0) > 0]
    scorers.sort(key=lambda p: p["goals"], reverse=True)
    return scorers[:n]


def match_analysis(model, home: str, away: str, neutral: bool = True):
    """מחזיר (pred, ctx, sections) לעמוד ניתוח משחק מורחב."""
    from prediction import review as rv
    pred = model.predict(home, away, neutral)
    ih, ia = team_info(home), team_info(away)
    ctx = {
        "pred": pred,
        "elo_home": ih.get("elo") or config.ELO_INITIAL,
        "elo_away": ia.get("elo") or config.ELO_INITIAL,
        "adj_home": config.CTS_WEIGHT * (ih.get("squad_adj") or 0.0),
        "adj_away": config.CTS_WEIGHT * (ia.get("squad_adj") or 0.0),
        "form_home": recent_form(home), "form_away": recent_form(away),
        "h2h": h2h_record(home, away),
        "players_home": top_scorers_of(home), "players_away": top_scorers_of(away),
    }
    return pred, ctx, rv.match_review(home, away, ctx)


def predict_lab(model, home, away, neutral=True, home_rest=None, away_rest=None,
                city=None, odds=None, home_locked=False, away_locked=False):
    """תחזית מלאה עם כל הגורמים (סעיפים 1-8) + פירוק שקוף."""
    from prediction import factors as F
    dh_total = da_total = 0.0
    breakdown = []
    contributions = [
        F.fatigue(home_rest, away_rest),
        F.altitude(home, away, city),
        F.head_to_head(home, away, h2h_matches(home, away)),
        F.dead_rubber(home_locked, away_locked),
    ]
    for dh, da, desc in contributions:
        if desc:
            dh_total += dh
            da_total += da
            breakdown.append({"factor": desc, "home": round(dh), "away": round(da)})

    p = model.predict(home, away, neutral, home_delta=dh_total, away_delta=da_total)
    result = {"pred": p, "breakdown": breakdown, "heat": F.heat_note(city),
              "elo_delta": (round(dh_total), round(da_total))}

    if odds and all(o and o > 1 for o in odds):
        op = F.odds_to_probs(*odds)
        if op:
            result["odds_probs"] = op
            result["blended"] = F.blend_with_odds(
                (p.p_home, p.p_draw, p.p_away), op)
            result["value"] = F.value_bets((p.p_home, p.p_draw, p.p_away), *odds)
    return result


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
    played = sum(1 for f in fixtures if f["played"])
    stored = _load_stored_sim()
    if stored:                       # טעינה מיידית מ-DB
        return stored, played, len(fixtures)
    probs = simulate.simulate(model, fixtures, team_groups(), n_runs=n_runs)
    return probs, played, len(fixtures)


def _load_stored_sim() -> dict | None:
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT t.name AS team, s.p_advance, s.p_round16, s.p_quarter, "
            "s.p_semi, s.p_final, s.p_winner, s.exp_goals FROM tournament_sim s "
            "JOIN teams t ON s.team_id = t.id"
        ).fetchall()
    if not rows:
        return None
    return {
        r["team"]: {"advance": r["p_advance"], "round16": r["p_round16"],
                    "quarter": r["p_quarter"], "semi": r["p_semi"],
                    "final": r["p_final"], "winner": r["p_winner"],
                    "exp_goals": r["exp_goals"] or 0.0}
        for r in rows
    }


def all_squads() -> dict[str, list[dict]]:
    """כל הסגלים מקובצים לפי נבחרת (לחישוב מלך שערים)."""
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT t.name AS team, sp.name AS pname, sp.pos, sp.goals, "
            "sp.caps, sp.club FROM squad_players sp "
            "JOIN teams t ON sp.team_id = t.id"
        ).fetchall()
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["team"], []).append({
            "name": r["pname"], "pos": r["pos"], "goals": r["goals"],
            "caps": r["caps"], "club": r["club"],
        })
    return out


def golden_boot(sim_probs: dict) -> list[dict]:
    """תחזית מלך שערים מהסגלים האמיתיים + פלט הסימולציה."""
    return scorers.golden_boot(sim_probs, all_squads())


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
