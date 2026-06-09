"""
מחולל סקירת משחק — טקסט מקצועי בעברית, מבוסס-נתונים.
מחזיר רשימת מקטעים (כותרת, HTML) לתצוגה עם unsafe_allow_html.

טיפול RTL: כל רכיב LTR (שם נבחרת/שחקן, מספר, תוצאה, טווח, אחוז) עטוף
בבידוד כיווני (<bdi> לשמות, dir=ltr למספרים/תוצאות) כדי שלא יתהפך.
"""
from __future__ import annotations

CONF_HE = {"high": "גבוהה", "medium": "בינונית", "low": "נמוכה"}
_RES_DOT = {"W": "🟢", "D": "⚪", "L": "🔴"}


def _t(x) -> str:
    """בידוד שם (אנגלית) — לא משבש את כיוון המשפט."""
    return f"<bdi>{x}</bdi>"


def _n(x) -> str:
    """כפיית LTR למספר / תוצאה / טווח / אחוז."""
    return f"<span dir='ltr'>{x}</span>"


def _gap_desc(gap: float) -> str:
    if gap >= 150:
        return "פער ניכר"
    if gap >= 70:
        return "יתרון מתון"
    return "כמעט שקול"


def _form_summary(form: list[dict]) -> tuple[int, int, int, str]:
    w = sum(1 for f in form if f["res"] == "W")
    d = sum(1 for f in form if f["res"] == "D")
    lo = sum(1 for f in form if f["res"] == "L")
    dots = " ".join(_RES_DOT[f["res"]] for f in form)
    return w, d, lo, dots


def match_review(home: str, away: str, ctx: dict) -> list[tuple[str, str]]:
    p = ctx["pred"]
    eh, ea = ctx["elo_home"], ctx["elo_away"]
    gap = abs(eh - ea)
    H, A = _t(home), _t(away)
    sections: list[tuple[str, str]] = []

    # הערכה כללית
    favored = home if p.p_home >= p.p_away else away
    fav_p = max(p.p_home, p.p_away)
    close = abs(p.p_home - p.p_away) < 0.10 and p.p_draw > 0.24
    if close:
        txt = (f"משחק צמוד שקשה לחיזוי — ההסתברויות קרובות וסיכוי התיקו גבוה "
               f"({_n(f'{p.p_draw*100:.0f}%')}). ")
    else:
        txt = f"<b>{_t(favored)}</b> היא הפייבוריטה עם {_n(f'{fav_p*100:.0f}%')} לניצחון. "
    txt += (f"דירוג Elo: {H} {_n(f'{eh:.0f}')} · {A} {_n(f'{ea:.0f}')} "
            f"({_gap_desc(gap)}).")
    sections.append(("📋 הערכה כללית", txt))

    # איך חושב החיזוי
    eff_h, eff_a = eh + ctx["adj_home"], ea + ctx["adj_away"]
    sections.append((
        "🧮 איך חושב החיזוי",
        f"המודל (Elo + Dixon-Coles) מחשב <b>דירוג אפקטיבי</b> לכל נבחרת — Elo היסטורי "
        f"+ התאמת כוח-סגל: {H} {_n(f'{eff_h:.0f}')} מול {A} {_n(f'{eff_a:.0f}')}. "
        f"מפער הכוחות ומנטיית ההתקפה/הגנה נגזרת <b>תוחלת השערים</b> "
        f"({_n(f'{p.exp_home_goals:.1f}–{p.exp_away_goals:.1f}')}), ומהתפלגות פואסון "
        f"מתקבלות ההסתברויות: ניצחון {_n(f'{p.p_home*100:.0f}%')} · "
        f"תיקו {_n(f'{p.p_draw*100:.0f}%')} · הפסד {_n(f'{p.p_away*100:.0f}%')}. "
        f"הפרמטרים מכוילים על מונדיאלים 2010–2022."))

    # כוח סגל
    ah, aa = ctx["adj_home"], ctx["adj_away"]
    if abs(ah - aa) >= 15:
        stronger = _t(home if ah > aa else away)
        sections.append(("💪 כוח סגל נוכחי",
                         f"ל<b>{stronger}</b> סגל חזק יותר — רוב שחקניה במועדונים בכירים "
                         f"יותר (יתרון של כ-{_n(f'{abs(ah-aa):.0f}')} נק' Elo)."))
    else:
        sections.append(("💪 כוח סגל נוכחי", "איכות הסגלים הנוכחיים דומה."))

    # טופס אחרון
    wh, dh, lh, sh = _form_summary(ctx["form_home"])
    wa, da, la, sa = _form_summary(ctx["form_away"])
    sections.append(("📈 טופס אחרון (5 משחקים)",
                     f"{H} — {_n(wh)} נצ' · {_n(dh)} תיקו · {_n(lh)} הפ'  {sh or '—'}<br>"
                     f"{A} — {_n(wa)} נצ' · {_n(da)} תיקו · {_n(la)} הפ'  {sa or '—'}"))

    # עימותים ישירים
    h = ctx["h2h"]
    if h["n"] > 0:
        sections.append(("🥊 עימותים ישירים",
                         f"מתוך {_n(h['n'])} מפגשים אחרונים: {H} ניצחה {_n(h['home_wins'])}, "
                         f"{A} ניצחה {_n(h['away_wins'])}, {_n(h['draws'])} תיקו."))
    else:
        sections.append(("🥊 עימותים ישירים", "אין היסטוריית מפגשים משמעותית."))

    # שחקני מפתח
    def _players(pl):
        return ", ".join(f"{_t(x['name'])} ({_n(x['goals'])} שע')" for x in pl) or "—"
    sections.append(("⭐ שחקני מפתח",
                     f"{H}: {_players(ctx['players_home'])}<br>"
                     f"{A}: {_players(ctx['players_away'])}"))

    # שורה תחתונה
    txt = (f"תוצאה צפויה: <b>{_n(p.likely_score)}</b> "
           f"(תוחלת {_n(f'{p.exp_home_goals:.1f}–{p.exp_away_goals:.1f}')}). "
           f"רמת ביטחון: <b>{CONF_HE.get(p.confidence, p.confidence)}</b>.")
    big = max(p.p_home_big, p.p_away_big)
    if big >= 0.15:
        who = _t(home if p.p_home_big >= p.p_away_big else away)
        txt += f" פוטנציאל לניצחון גדול ל{who} ({_n(f'{big*100:.0f}%')} ל-3+ שערים)."
    sections.append(("🔮 שורה תחתונה", txt))
    return sections
