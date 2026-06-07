"""
רענון מלא של המערכת (שלב 6) — קליטה, Elo, ותחזיות.
הרצה:  python -m scripts.refresh

בעתיד אפשר לתזמן אוטומטית (Windows Task Scheduler / APScheduler)
שיריץ פקודה זו אחת ליום במהלך הטורניר.
"""
from __future__ import annotations

from datetime import datetime

import config
import update


def main() -> None:
    print("=" * 50)
    print("רענון מלא — מערכת חיזוי מונדיאל")
    print("=" * 50)
    summary = update.full_refresh()
    print(f"[OK] נבחרות: {summary['teams']}")
    print(f"[OK] תוצאות היסטוריות: {summary['historical_matches']:,}")
    print(f"[OK] משחקי טורניר: {summary['fixtures']}")
    print(f"[OK] תוצאות 2026 שהוזרמו להיסטוריה: {summary['played_synced']}")
    print(f"[OK] דירוגי Elo עודכנו: {summary['ratings']}")
    print(f"[OK] snapshots תחזית נשמרו: {summary['predictions']}")
    print(f"[OK] פציעות: {summary.get('injuries', 0)}")

    # רישום לקובץ log (שימושי כשרץ אוטומטית ברקע)
    stamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    line = (f"{stamp} | משחקים={summary['fixtures']} שוחקו+={summary['played_synced']} "
            f"Elo={summary['ratings']} תחזיות={summary['predictions']} "
            f"פציעות={summary.get('injuries', 0)}\n")
    with open(config.DATA_DIR / "refresh.log", "a", encoding="utf-8") as fh:
        fh.write(line)


if __name__ == "__main__":
    main()
