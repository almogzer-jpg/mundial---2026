"""
קליטת נתונים (שלב 1) — מושך נתונים פתוחים ל-DB ומדפיס סיכום.
הרצה מתיקיית השורש:  python -m scripts.ingest
"""
from __future__ import annotations

from collections import defaultdict

from data import db
from ingestion import loader


def main() -> None:
    print("=" * 55)
    print("קליטת נתונים — מונדיאל 2026 (מקורות פתוחים)")
    print("=" * 55)

    summary = loader.run()
    print(f"[OK] נבחרות: {summary['teams']}")
    print(f"[OK] תוצאות היסטוריות: {summary['historical_matches']:,}")
    print(f"[OK] משחקי הטורניר: {summary['fixtures']}")

    with db.connection() as conn:
        # בתים
        print("\n--- שיוך בתים ---")
        rows = conn.execute(
            "SELECT grp, name FROM teams ORDER BY grp, name"
        ).fetchall()
        by_group = defaultdict(list)
        for r in rows:
            by_group[r["grp"]].append(r["name"])
        for g in sorted(by_group):
            print(f"  בית {g}: {', '.join(by_group[g])}")

        # טווח תאריכים היסטורי
        rng = conn.execute(
            "SELECT MIN(date), MAX(date) FROM historical_matches"
        ).fetchone()
        print(f"\n--- היסטוריה: {rng[0]} עד {rng[1]} ---")

        # דוגמת משחקים קרובים
        print("\n--- 5 המשחקים הראשונים בטורניר ---")
        sample = conn.execute(
            "SELECT f.date_utc, f.grp, h.name AS home, a.name AS away, f.city "
            "FROM fixtures f "
            "JOIN teams h ON f.home_team_id = h.id "
            "JOIN teams a ON f.away_team_id = a.id "
            "ORDER BY f.date_utc LIMIT 5"
        ).fetchall()
        for s in sample:
            d = s["date_utc"]
            # תצוגה DD/MM/YYYY
            try:
                y, m, day = d.split("-")
                d = f"{day}/{m}/{y}"
            except ValueError:
                pass
            print(f"  {d} | בית {s['grp']} | {s['home']} נגד {s['away']} @ {s['city']}")


if __name__ == "__main__":
    main()
