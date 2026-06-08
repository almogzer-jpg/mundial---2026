"""
מתזמר העדכון המתגלגל — הלב של "המערכת לומדת מהתוצאות".

זרימה מלאה (full_refresh):
  1. קליטה מחדש (פתוח + ידני) — תוצאות שהוזנו נכנסות ל-fixtures.
  2. הזרמת משחקי 2026 שהושלמו אל historical_matches — כדי שיזינו Elo/חוזקים.
  3. בנייה מחדש של Elo (teams.elo + elo_history).
  4. שמירת snapshot תחזית לכל משחק שטרם שוחק (predictions).

מופעל ידנית (מהדשבורד או scripts/refresh.py). כשיחובר API בעתיד,
אותו תהליך ירוץ אוטומטית — ללא שינוי בלוגיקה.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import config
from data import db
from ingestion import loader
from prediction import engine
from ratings.elo import EloEngine


def sync_played_to_history(conn) -> int:
    """מזרים משחקי 2026 שהושלמו אל טבלת ההיסטוריה (מזינים Elo)."""
    rows = conn.execute(
        "SELECT f.date_utc, h.name AS home, a.name AS away, "
        "f.home_goals, f.away_goals, f.is_neutral, f.round "
        "FROM fixtures f JOIN teams h ON f.home_team_id = h.id "
        "JOIN teams a ON f.away_team_id = a.id "
        "WHERE f.home_goals IS NOT NULL"
    ).fetchall()
    n = 0
    for r in rows:
        tour = "FIFA World Cup"
        conn.execute(
            "INSERT OR REPLACE INTO historical_matches "
            "(date, home_team, away_team, home_score, away_score, tournament, neutral) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (r["date_utc"], r["home"], r["away"], r["home_goals"],
             r["away_goals"], tour, r["is_neutral"]),
        )
        n += 1
    return n


def rebuild_ratings(conn) -> int:
    """מחשב Elo מחדש מכל ההיסטוריה ושומר ל-teams + elo_history."""
    rows = conn.execute(
        "SELECT date, home_team, away_team, home_score, away_score, "
        "tournament, neutral FROM historical_matches ORDER BY date"
    ).fetchall()
    wc_teams = {r["name"]: r["id"]
                for r in conn.execute("SELECT id, name FROM teams").fetchall()}

    engine_elo = EloEngine()
    history = []
    for m in rows:
        d_home, _ = engine_elo.update_match(
            m["home_team"], m["away_team"], m["home_score"], m["away_score"],
            m["tournament"], bool(m["neutral"]),
        )
        for team, delta in ((m["home_team"], d_home), (m["away_team"], -d_home)):
            if team in wc_teams:
                history.append((wc_teams[team], m["date"],
                                round(engine_elo.get(team), 2), round(delta, 2)))

    for name, tid in wc_teams.items():
        conn.execute("UPDATE teams SET elo = ? WHERE id = ?",
                     (round(engine_elo.get(name), 2), tid))
    conn.execute("DELETE FROM elo_history")
    conn.executemany(
        "INSERT INTO elo_history (team_id, date, rating, change) VALUES (?, ?, ?, ?)",
        history,
    )
    return len(wc_teams)


def sync_squads(conn) -> int:
    """מושך סגלי 2026 מויקיפדיה, שומר, ומחשב התאמות כוח-סגל ל-teams."""
    from ingestion.squads import parse_squads
    from prediction import squad as sq
    try:
        squads = parse_squads()
    except Exception:
        return 0
    name_to_id = {r["name"]: r["id"]
                  for r in conn.execute("SELECT id, name FROM teams").fetchall()}
    squads = {t: ps for t, ps in squads.items() if t in name_to_id}
    if not squads:
        return 0
    adj = sq.compute_adjustments(squads)
    conn.execute("DELETE FROM squad_players")
    n = 0
    for team, players in squads.items():
        tid = name_to_id[team]
        for p in players:
            conn.execute(
                "INSERT INTO squad_players "
                "(team_id, name, pos, age, caps, goals, club, clubnat, rating) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tid, p.name, p.pos, p.age, p.caps, p.goals, p.club, p.clubnat,
                 round(sq.player_rating(p.clubnat, p.club), 1)),
            )
            n += 1
        a = adj[team]
        conn.execute(
            "UPDATE teams SET ssi = ?, squad_adj = ?, squad_n = ? WHERE id = ?",
            (round(a["ssi"], 1), a["squad_adj"], a["n"], tid),
        )
    return n


def store_predictions(conn, model) -> int:
    """
    שומר snapshot תחזית לכל משחק שטרם שוחק (NS).
    משחקים שהושלמו שומרים את ה-snapshot האחרון שנעשה לפניהם (לא נדרס) —
    כך אפשר להשוות בדיעבד תחזית מול תוצאה.
    """
    fixtures = conn.execute(
        "SELECT f.id, h.name AS home, a.name AS away, f.is_neutral, f.home_goals "
        "FROM fixtures f JOIN teams h ON f.home_team_id = h.id "
        "JOIN teams a ON f.away_team_id = a.id"
    ).fetchall()
    now = datetime.now(timezone.utc).isoformat()
    n = 0
    for f in fixtures:
        if f["home_goals"] is not None:
            continue  # שוחק - לא דורסים את התחזית שקדמה לו
        p = model.predict(f["home"], f["away"], neutral=bool(f["is_neutral"]))
        conn.execute("DELETE FROM predictions WHERE fixture_id = ?", (f["id"],))
        conn.execute(
            "INSERT INTO predictions (fixture_id, created_at, p_home, p_draw, p_away, "
            "exp_home_goals, exp_away_goals, likely_score, top_scores, confidence, "
            "model_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f["id"], now, p.p_home, p.p_draw, p.p_away, p.exp_home_goals,
             p.exp_away_goals, p.likely_score, json.dumps(p.top_scores),
             p.confidence, config.MODEL_VERSION),
        )
        n += 1
    return n


def full_refresh() -> dict:
    """מריץ את כל שרשרת העדכון ומחזיר סיכום."""
    summary = loader.run()                       # 1. קליטה מחדש
    with db.connection() as conn:
        played = sync_played_to_history(conn)    # 2. הזרמה להיסטוריה
        teams = rebuild_ratings(conn)            # 3. Elo מחדש
        squads = sync_squads(conn)               # 4. כוח סגל נוכחי (ויקיפדיה)
    model = engine.build_model(date.today())     # מודל על נתונים טריים
    with db.connection() as conn:
        preds = store_predictions(conn, model)   # 5. snapshots
    summary.update({"played_synced": played, "ratings": teams,
                    "squad_players": squads, "predictions": preds})
    return summary


if __name__ == "__main__":
    print("מריץ עדכון מלא...")
    print("סיכום:", full_refresh())
