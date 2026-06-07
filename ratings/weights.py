"""
משקלי משחק — חשיבות + עדכניות.

שני סוגי משקל, מקור אמת אחד:
  • חשיבות (importance): כמה "נחשב" סוג המשחק. משמש גם ל-K של Elo
    (K = importance × ELO_K_MAX) וגם כמשקל במודל ה-Poisson.
  • עדכניות (recency): דעיכה מעריכית לפי גיל המשחק. משמש את מודל ה-Poisson.

הערכים הם נקודות פתיחה סבירות (מבוססי World Football Elo) ויכוילו ב-Backtest.
"""
from __future__ import annotations

from datetime import date

# --- משקלי חשיבות יחסיים (0..1) לפי קטגוריה ---
IMPORTANCE = {
    "wc_knockout":      1.00,   # מונדיאל - נוקאאוט
    "wc_group":         0.90,   # מונדיאל - שלב בתים
    "wc_finals":        0.95,   # מונדיאל ללא מידע שלב (היסטורי)
    "continental":      0.80,   # יורו / קופה אמריקה / אסיה / אפריקה / גולד קאפ
    "confederations":   0.75,   # גביע הקונפדרציות
    "qualifier":        0.60,   # מוקדמות (מונדיאל / יבשתיות)
    "nations_league":   0.60,   # ליגת האומות
    "other_official":   0.50,   # טורנירים רשמיים אחרים
    "friendly":         0.30,   # ידידות
}

# מילות מפתח לזיהוי קטגוריה (הסדר חשוב: בודקים ספציפי לפני כללי)
_CONTINENTAL_KEYWORDS = (
    "uefa euro", "copa am", "african cup", "africa cup", "afc asian cup",
    "asian cup", "gold cup", "concacaf championship", "oceania nations",
    "nations cup",
)


def classify(tournament: str, round_name: str | None = None) -> str:
    """ממיר את שם הטורניר (+ שלב אופציונלי) לקטגוריית חשיבות."""
    t = (tournament or "").lower().strip()
    r = (round_name or "").lower()

    if "friendly" in t:
        return "friendly"
    if "qualif" in t:                       # כל סוגי המוקדמות
        return "qualifier"
    if "nations league" in t:
        return "nations_league"
    if "confederations" in t:
        return "confederations"
    if "world cup" in t:                    # מונדיאל (לא מוקדמות - נבדק כבר)
        if "knockout" in r or any(
            k in r for k in ("final", "semi", "quarter", "round of", "16", "32")
        ):
            return "wc_knockout"
        if "group" in r:
            return "wc_group"
        return "wc_finals"                  # אין מידע שלב (היסטורי)
    if any(k in t for k in _CONTINENTAL_KEYWORDS):
        return "continental"
    # שאר טורנירים רשמיים (לא ידידות, לא מזוהה אחרת)
    return "other_official"


def importance_weight(tournament: str, round_name: str | None = None) -> float:
    """משקל החשיבות היחסי (0..1) של משחק."""
    return IMPORTANCE[classify(tournament, round_name)]


def recency_weight(match_date: date, ref_date: date, half_life_days: float) -> float:
    """דעיכה מעריכית: 1.0 להיום, יורד בחצי בכל מחצית-חיים."""
    age_days = max(0, (ref_date - match_date).days)
    return 0.5 ** (age_days / half_life_days)
