"""
בניית דירוגי Elo (שלב 2) — מחשב Elo מכל ההיסטוריה, שומר ל-DB, ומדפיס דירוג.
הרצה מתיקיית השורש:  python -m scripts.build_ratings
"""
from __future__ import annotations

from collections import namedtuple
from datetime import datetime, timezone

import config
from data import db
from ratings.elo import EloEngine

Match = namedtuple(
    "Match",
    "date home_team away_team home_score away_score tournament neutral",
)


def load_matches(conn) -> list[Match]:
    rows = conn.execute(
        "SELECT date, home_team, away_team, home_score, away_score, "
        "tournament, neutral FROM historical_matches ORDER BY date"
    ).fetchall()
    return [Match(*r) for r in rows]


def main() -> None:
    print("=" * 55)
    print("בניית דירוגי Elo — שלב 2")
    print("=" * 55)

    with db.connection() as conn:
        matches = load_matches(conn)
        wc_teams = {
            r["name"]: r["id"]
            for r in conn.execute("SELECT id, name FROM teams").fetchall()
        }
        print(f"מעבד {len(matches):,} משחקים היסטוריים...")

        engine = EloEngine()
        history = []  # snapshots לנבחרות המונדיאל בלבד
        for m in matches:  # כבר ממוין לפי תאריך
            d_home, _ = engine.update_match(
                m.home_team, m.away_team, m.home_score, m.away_score,
                m.tournament, bool(m.neutral),
            )
            for team, delta in ((m.home_team, d_home), (m.away_team, -d_home)):
                if team in wc_teams:
                    history.append(
                        (wc_teams[team], m.date, round(engine.get(team), 2),
                         round(delta, 2))
                    )

        # שמירת דירוג סופי ל-48 הנבחרות
        for name, tid in wc_teams.items():
            conn.execute(
                "UPDATE teams SET elo = ? WHERE id = ?",
                (round(engine.get(name), 2), tid),
            )

        # שמירת היסטוריית Elo
        conn.execute("DELETE FROM elo_history")
        conn.executemany(
            "INSERT INTO elo_history (team_id, date, rating, change) "
            "VALUES (?, ?, ?, ?)",
            history,
        )

    print(f"[OK] חושב Elo ל-{len(engine.ratings):,} נבחרות (כולל יריבים היסטוריים)")
    print(f"[OK] נשמר דירוג ל-{len(wc_teams)} נבחרות מונדיאל + {len(history):,} snapshots")

    # --- בדיקת שפיות: טופ 20 עולמי ---
    top = sorted(engine.ratings.items(), key=lambda kv: kv[1], reverse=True)[:20]
    print("\n--- טופ 20 עולמי (Elo) ---")
    for i, (team, rating) in enumerate(top, 1):
        mark = " ★" if team in wc_teams else ""
        print(f"  {i:2}. {team:24} {rating:7.1f}{mark}")

    # --- דירוג נבחרות המונדיאל ---
    wc_ranked = sorted(
        ((n, engine.get(n)) for n in wc_teams), key=lambda kv: kv[1], reverse=True
    )
    print("\n--- 10 נבחרות המונדיאל המדורגות ביותר ---")
    for i, (team, rating) in enumerate(wc_ranked[:10], 1):
        print(f"  {i:2}. {team:24} {rating:7.1f}")


if __name__ == "__main__":
    main()
