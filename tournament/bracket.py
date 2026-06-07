"""
בניית עץ הנוקאאוט — פורמט מונדיאל 2026 (48 קבוצות).

מעפילים לשלב ה-32:
  • 12 מנצחות בתים
  • 12 סגניות
  • 8 השלישיות הטובות ביותר (מדורגות לפי נק' -> הפרש -> זכות)

מבנה הבראקט: 32 המעפילים מזורעים לפי ביצועי שלב הבתים, ומשובצים
בעץ single-elimination סטנדרטי (מזרע מס' 1 פוגש את האחרון וכו'),
כך ששמירת הזרע מרחיקה את החזקות זו מזו. זוהי קירוב סביר של הבראקט
הרשמי (טבלת השיבוץ הרשמית של השלישיות מורכבת מאוד) — מתאים לסימולציה.
"""
from __future__ import annotations

import math

from tournament.standings import Row


def _stat_key(row: Row) -> tuple:
    return (row.points, row.gd, row.gf)


def qualifiers(standings: dict[str, list[Row]]) -> dict:
    """מחזיר את המעפילים: מנצחות, סגניות, ו-8 השלישיות הטובות."""
    winners, runners, thirds = {}, {}, []
    for g, table in standings.items():
        if len(table) >= 1:
            winners[g] = table[0].team
        if len(table) >= 2:
            runners[g] = table[1].team
        if len(table) >= 3:
            thirds.append((g, table[2]))
    # דירוג השלישיות, 8 הטובות עולות
    thirds_ranked = sorted(thirds, key=lambda gt: _stat_key(gt[1]), reverse=True)
    best_thirds = [t for _, t in thirds_ranked[:8]]
    return {
        "winners": winners,
        "runners": runners,
        "best_thirds": [r.team for r in best_thirds],
        "thirds_ranked": thirds_ranked,
    }


def _bracket_seed_positions(n: int) -> list[int]:
    """סדר זרעים סטנדרטי לעץ בגודל n (חזקת 2): מרחיק זרעים גבוהים."""
    seeds = [1, 2]
    while len(seeds) < n:
        m = len(seeds) * 2 + 1
        expanded = []
        for s in seeds:
            expanded.append(s)
            expanded.append(m - s)
        seeds = expanded
    return seeds


def seed_qualifiers(quals: dict, standings: dict[str, list[Row]]) -> list[str]:
    """
    מדרג את 32 המעפילים לזרעים 1..32.
    ציון זרע: מנצחות מעל סגניות מעל שלישיות, ובתוך כל קבוצה לפי נק'/הפרש/זכות.
    """
    # מפה team -> Row (לסטטיסטיקה)
    stat = {}
    for table in standings.values():
        for row in table:
            stat[row.team] = row

    def score(team: str, tier: int) -> tuple:
        r = stat.get(team)
        base = (r.points, r.gd, r.gf) if r else (0, 0, 0)
        return (tier, *base)

    pool = []
    for t in quals["winners"].values():
        pool.append((t, score(t, 3)))   # tier 3 = מנצחת
    for t in quals["runners"].values():
        pool.append((t, score(t, 2)))   # tier 2 = סגנית
    for t in quals["best_thirds"]:
        pool.append((t, score(t, 1)))   # tier 1 = שלישית

    pool.sort(key=lambda ts: ts[1], reverse=True)
    return [t for t, _ in pool]   # מדורג 1..32


def build_r32(seeded: list[str]) -> list[tuple[str, str]]:
    """בונה את 16 זוגות שלב ה-32 לפי זריעה סטנדרטית."""
    n = len(seeded)
    if n < 2:
        return []
    positions = _bracket_seed_positions(n)            # רשימת מס' זרעים בסדר העץ
    seat = [seeded[p - 1] for p in positions]         # team בכל מושב בעץ
    return [(seat[i], seat[i + 1]) for i in range(0, n, 2)]


ROUND_NAMES = {32: "Round of 32", 16: "Round of 16", 8: "Quarter-final",
               4: "Semi-final", 2: "Final"}
