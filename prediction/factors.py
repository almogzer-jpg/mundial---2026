"""
גורמים ברמת משחק (סעיפים 1-8) — התאמות קטנות ושקופות לדירוג, פר-משחק.

כל גורם מחזיר (delta_home, delta_away) בנק' Elo + תיאור מילולי לתצוגה.
המשקלים שמרניים בכוונה: ה-Backtest מראה שהשפעתם המצרפית קטנה, אז הם
משמשים בעיקר לשקיפות ולמקרים ספציפיים — בלי להציף את הליבה המכוילת.

מקורות חינמיים: לוח המשחקים (עייפות), טבלת ערים (גובה), ההיסטוריה (H2H),
הטבלה (מוטיבציה). הרכב/פציעות/הימורים — הזנה ידנית.
"""
from __future__ import annotations

import config

# גובה ערים מארחות (מטרים) — רק אלה מעל הסף משפיעים
CITY_ALTITUDE = {
    "mexico city": 2240, "guadalajara": 1566, "zapopan": 1566,
    "monterrey": 540, "guadalupe": 540,
}
# ערים חמות (לחות/חום קיצי) — מוצג כהקשר בלבד (ללא שינוי Elo)
HOT_CITIES = {"dallas", "arlington", "houston", "miami", "miami gardens",
              "atlanta", "kansas city", "monterrey", "guadalupe"}
# נבחרות מותאמות-גובה (לא נענשות בגובה)
ALTITUDE_ACCLIMATIZED = {"Mexico", "Bolivia", "Ecuador", "Colombia", "Peru"}


def fatigue(home_rest: int | None, away_rest: int | None) -> tuple[float, float, str]:
    if home_rest is None or away_rest is None:
        return 0.0, 0.0, ""
    diff = max(-config.FATIGUE_MAX_DAYS,
               min(config.FATIGUE_MAX_DAYS, home_rest - away_rest))
    delta = config.FATIGUE_ELO_PER_DAY * diff
    if abs(delta) < 1:
        return 0.0, 0.0, ""
    return delta, -delta, f"עייפות (מנוחה {home_rest} מול {away_rest} ימים)"


def altitude(home: str, away: str, city: str | None) -> tuple[float, float, str]:
    if not city:
        return 0.0, 0.0, ""
    alt = CITY_ALTITUDE.get(city.strip().lower(), 0)
    if alt < config.ALTITUDE_THRESHOLD_M:
        return 0.0, 0.0, ""
    dh = 0.0 if home in ALTITUDE_ACCLIMATIZED else -config.ALTITUDE_PENALTY
    da = 0.0 if away in ALTITUDE_ACCLIMATIZED else -config.ALTITUDE_PENALTY
    if dh == da:
        return 0.0, 0.0, ""
    return dh - da, da - dh, f"גובה {alt}מ' ב{city}"


def heat_note(city: str | None) -> str:
    if city and city.strip().lower() in HOT_CITIES:
        return f"⚠️ חום/לחות גבוהים ב{city} (הקשר בלבד)"
    return ""


def head_to_head(home: str, away: str, h2h_matches: list[dict]) -> tuple[float, float, str]:
    """
    h2h_matches: רשימת {home, away, hs, as} של עימותים ישירים היסטוריים.
    התאמה קטנה ומכווצת לפי הפרש השערים הממוצע ביניהם.
    """
    if not h2h_matches:
        return 0.0, 0.0, ""
    margin = 0
    for m in h2h_matches:
        gd = m["hs"] - m["as"]
        margin += gd if m["home"] == home else -gd
    n = len(h2h_matches)
    avg = margin / (n + config.H2H_SHRINK)        # ריכוך למדגם קטן
    delta = max(-config.H2H_MAX_DELTA, min(config.H2H_MAX_DELTA, avg * 15))
    if abs(delta) < 1:
        return 0.0, 0.0, ""
    return delta, -delta, f"עימותים ישירים ({n} משחקים)"


def dead_rubber(home_locked: bool, away_locked: bool) -> tuple[float, float, str]:
    """
    'locked' = הקבוצה כבר הבטיחה/איבדה את גורלה (משחק חסר משמעות עבורה).
    קבוצה ש'גורלה נחתם' מאבדת מעט מהעליונות (מוטיבציה/רוטציה).
    """
    if home_locked == away_locked:
        return 0.0, 0.0, ""
    if home_locked:
        return -25.0, 25.0, "משחק חסר משמעות לבית (רוטציה צפויה)"
    return 25.0, -25.0, "משחק חסר משמעות לחוץ (רוטציה צפויה)"


# --- יחסי הימורים ---
def odds_to_probs(o_home: float, o_draw: float, o_away: float) -> tuple[float, float, float] | None:
    """יחסים עשרוניים -> הסתברויות מנוקות-מרווח (devig)."""
    try:
        inv = [1 / o_home, 1 / o_draw, 1 / o_away]
    except (ZeroDivisionError, TypeError):
        return None
    s = sum(inv)
    if s <= 0:
        return None
    return tuple(x / s for x in inv)


def blend_with_odds(model_probs, odds_probs, w: float = None):
    """מיזוג הסתברויות המודל עם הסתברויות השוק."""
    w = config.ODDS_BLEND if w is None else w
    return tuple((1 - w) * mp + w * op for mp, op in zip(model_probs, odds_probs))


def value_bets(model_probs, o_home, o_draw, o_away) -> list[str]:
    """מזהה הימורי ערך: הסתברות המודל × היחס > 1 => ערך חיובי."""
    labels = ["בית", "תיקו", "חוץ"]
    odds = [o_home, o_draw, o_away]
    out = []
    for lbl, p, o in zip(labels, model_probs, odds):
        if o and p * o > 1.05:                # 5%+ ערך
            out.append(f"{lbl}: ערך +{(p*o-1)*100:.0f}% (מודל {p*100:.0f}%, יחס {o})")
    return out
