"""
הדגמת סימולציית טורניר (שלב 4).
הרצה:  python -m scripts.simulate_demo [n_runs]
"""
from __future__ import annotations

import sys
import time

from data import db
from prediction import engine
from tournament import simulate


def main() -> None:
    n_runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"בונה מודל ומריץ {n_runs:,} סימולציות...")

    model = engine.build_model()
    with db.connection() as conn:
        fixtures = simulate.group_fixtures_from_db(conn)
        team_groups = {
            r["name"]: r["grp"]
            for r in conn.execute(
                "SELECT name, grp FROM teams WHERE grp IS NOT NULL"
            ).fetchall()
        }

    played = sum(1 for f in fixtures if f["played"])
    print(f"משחקי בתים: {len(fixtures)} (שוחקו: {played})")

    t0 = time.time()
    probs = simulate.simulate(model, fixtures, team_groups, n_runs=n_runs)
    print(f"הסתיים ב-{time.time()-t0:.1f} שניות.\n")

    ranked = sorted(probs.items(), key=lambda kv: kv[1]["winner"], reverse=True)
    print("--- 12 המועמדות לזכייה בגביע ---")
    print(f"{'נבחרת':22} {'אלופה':>7} {'גמר':>7} {'8 אחרונות':>10} {'עולה':>7}")
    for team, p in ranked[:12]:
        print(f"{team:22} {p['winner']*100:6.1f}% {p['final']*100:6.1f}% "
              f"{p['quarter']*100:9.1f}% {p['advance']*100:6.1f}%")


if __name__ == "__main__":
    main()
