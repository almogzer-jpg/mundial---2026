"""
בדיקת תקינות התשתית: אתחול DB, טעינת מודולים, ובדיקת חיבור API (אם יש מפתח).
הרצה מתיקיית השורש:  python -m scripts.check_setup
"""
from __future__ import annotations

import config
from data import db
from ingestion.api_football import APIFootballClient, APIFootballError


def main() -> None:
    print("=" * 50)
    print("בדיקת תשתית — מערכת חיזוי מונדיאל")
    print("=" * 50)

    # 1. אתחול DB
    db.init_db()
    print(f"[OK] מסד נתונים אותחל: {config.DB_PATH}")

    with db.connection() as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
    print(f"[OK] נוצרו {len(tables)} טבלאות:")
    for t in tables:
        print(f"      - {t}")

    # 2. בדיקת מפתח API
    if not config.API_FOOTBALL_KEY:
        print("[--] עדיין אין מפתח API ב-.env (זה בסדר בשלב זה).")
        print("     כשיהיה מפתח: העתק .env.example ל-.env, מלא אותו, והרץ שוב.")
        return

    # 3. בדיקת חיבור חי
    print(f"[..] בודק חיבור ל-API (ספק: {config.API_FOOTBALL_PROVIDER})...")
    try:
        client = APIFootballClient()
        info = client.status()
        if info:
            acct = info[0].get("account", {})
            sub = info[0].get("subscription", {})
            req = info[0].get("requests", {})
            print(f"[OK] מחובר! חשבון: {acct.get('firstname', '')} "
                  f"| מסלול: {sub.get('plan', '?')}")
            print(f"     בקשות היום: {req.get('current', '?')}/{req.get('limit_day', '?')}")
        else:
            print("[??] החיבור עבר אך לא הוחזר מידע סטטוס.")
    except APIFootballError as exc:
        print(f"[!!] בעיית חיבור ל-API: {exc}")


if __name__ == "__main__":
    main()
