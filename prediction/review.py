"""
מחולל סקירת משחק — טקסט מקצועי בעברית, מבוסס-נתונים.
מקבל הקשר (תחזית, Elo, כוח-סגל, טופס, עימותים, שחקנים) ומחזיר
רשימת מקטעים (כותרת, טקסט) לתצוגה.
"""
from __future__ import annotations

CONF_HE = {"high": "גבוהה", "medium": "בינונית", "low": "נמוכה"}
_RES_HE = {"W": "נ", "D": "ת", "L": "ה"}


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
    seq = "".join(_RES_HE[f["res"]] for f in form)   # מהאחרון לישן
    return w, d, lo, seq


def match_review(home: str, away: str, ctx: dict) -> list[tuple[str, str]]:
    p = ctx["pred"]
    eh, ea = ctx["elo_home"], ctx["elo_away"]
    gap = abs(eh - ea)
    sections: list[tuple[str, str]] = []

    # הערכה כללית
    favored = home if p.p_home >= p.p_away else away
    fav_p = max(p.p_home, p.p_away)
    close = abs(p.p_home - p.p_away) < 0.10 and p.p_draw > 0.24
    if close:
        txt = (f"משחק צמוד שקשה לחיזוי — ההסתברויות קרובות וסיכוי התיקו גבוה "
               f"({p.p_draw*100:.0f}%). ")
    else:
        txt = f"**{favored}** היא הפייבוריטה עם {fav_p*100:.0f}% לניצחון. "
    txt += f"דירוג Elo: {home} {eh:.0f} · {away} {ea:.0f} ({_gap_desc(gap)})."
    sections.append(("📋 הערכה כללית", txt))

    # איך חושב החיזוי (מתודולוגיה למשחק זה)
    eff_h = eh + ctx["adj_home"]
    eff_a = ea + ctx["adj_away"]
    sections.append((
        "🧮 איך חושב החיזוי",
        f"המודל (Elo + Dixon-Coles) מחשב **דירוג אפקטיבי** לכל נבחרת — "
        f"Elo היסטורי + התאמת כוח-סגל: {home} {eff_h:.0f} מול {away} {eff_a:.0f}. "
        f"מפער הכוחות ומנטיית ההתקפה/הגנה נגזרת **תוחלת השערים** "
        f"({p.exp_home_goals:.1f}-{p.exp_away_goals:.1f}), ומהתפלגות פואסון של התוצאות "
        f"מתקבלות ההסתברויות: ניצחון {p.p_home*100:.0f}% · תיקו {p.p_draw*100:.0f}% · "
        f"הפסד {p.p_away*100:.0f}%. הפרמטרים מכוילים על מונדיאלים 2010–2022."))

    # כוח סגל
    ah, aa = ctx["adj_home"], ctx["adj_away"]
    if abs(ah - aa) >= 15:
        stronger = home if ah > aa else away
        sections.append(("💪 כוח סגל נוכחי",
                         f"ל**{stronger}** סגל חזק יותר — רוב שחקניה במועדונים בכירים "
                         f"יותר (יתרון של כ-{abs(ah-aa):.0f} נק' Elo בשקלול)."))
    else:
        sections.append(("💪 כוח סגל נוכחי", "איכות הסגלים הנוכחיים דומה."))

    # טופס אחרון
    wh, dh, lh, sh = _form_summary(ctx["form_home"])
    wa, da, la, sa = _form_summary(ctx["form_away"])
    sections.append(("📈 טופס אחרון (5 משחקים)",
                     f"{home}: {wh} נצ' / {dh} תיקו / {lh} הפ' — {sh or '—'}\n\n"
                     f"{away}: {wa} נצ' / {da} תיקו / {la} הפ' — {sa or '—'}"))

    # עימותים ישירים
    h = ctx["h2h"]
    if h["n"] > 0:
        sections.append(("🥊 עימותים ישירים",
                         f"מתוך {h['n']} מפגשים אחרונים: {home} ניצחה {h['home_wins']}, "
                         f"{away} ניצחה {h['away_wins']}, {h['draws']} תיקו."))
    else:
        sections.append(("🥊 עימותים ישירים", "אין היסטוריית מפגשים משמעותית."))

    # שחקני מפתח
    def _players(pl):
        return ", ".join(f"{x['name']} ({x['goals']} שע')" for x in pl) or "—"
    sections.append(("⭐ שחקני מפתח",
                     f"{home}: {_players(ctx['players_home'])}\n\n"
                     f"{away}: {_players(ctx['players_away'])}"))

    # שורה תחתונה
    txt = (f"תוצאה צפויה: **{p.likely_score}** (תוחלת {p.exp_home_goals:.1f}-"
           f"{p.exp_away_goals:.1f}). רמת ביטחון: **{CONF_HE.get(p.confidence, p.confidence)}**.")
    big = max(p.p_home_big, p.p_away_big)
    if big >= 0.15:
        who = home if p.p_home_big >= p.p_away_big else away
        txt += f" פוטנציאל לניצחון גדול ל{who} ({big*100:.0f}% ל-3+ שערים)."
    sections.append(("🔮 שורה תחתונה", txt))
    return sections
