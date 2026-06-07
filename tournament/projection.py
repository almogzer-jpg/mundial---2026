"""
בראקט נוקאאוט חזוי — "המסלול הסביר ביותר".

1. מדרג כל בית לפי נקודות צפויות (מהמודל; תוצאות בפועל אם כבר שוחקו).
2. קובע מעפילים: 12 מנצחות + 12 סגניות + 8 שלישיות טובות.
3. מזריע ובונה את שלב ה-32.
4. "משחק" כל שלב לפי המנצח החזוי (הסתברות גבוהה יותר) עד אלוף.

מתעדכן אוטומטית: ככל שמוזנות תוצאות, הדירוג והעץ משתנים.
"""
from __future__ import annotations

from collections import defaultdict

import config
from tournament import bracket

ROUND_NAMES = ["שלב 32", "שמינית גמר", "רבע גמר", "חצי גמר", "גמר"]


def projected_group_order(model, group_fixtures, team_groups):
    """מחזיר {group: [teams בסדר צפוי]} + ניקוד צפוי לכל קבוצה."""
    exp_pts = defaultdict(float)
    for f in group_fixtures:
        h, a = f["home"], f["away"]
        if f.get("played") and f["hs"] is not None:
            if f["hs"] > f["as"]:
                exp_pts[h] += 3
            elif f["hs"] < f["as"]:
                exp_pts[a] += 3
            else:
                exp_pts[h] += 1
                exp_pts[a] += 1
        else:
            p = model.predict(h, a, neutral=True)
            exp_pts[h] += 3 * p.p_home + p.p_draw
            exp_pts[a] += 3 * p.p_away + p.p_draw

    groups = defaultdict(list)
    for team, g in team_groups.items():
        groups[g].append(team)

    elo = model.elo
    order = {}
    for g, teams in groups.items():
        order[g] = sorted(teams, key=lambda t: (exp_pts[t], elo.get(t, config.ELO_INITIAL)),
                          reverse=True)
    return order, exp_pts


def projected_bracket(model, group_fixtures, team_groups):
    """מחזיר (rounds, champion). rounds = [{'name','matches':[{home,away,winner,prob}]}]."""
    order, exp_pts = projected_group_order(model, group_fixtures, team_groups)
    elo = model.elo

    winners = [order[g][0] for g in order if len(order[g]) >= 1]
    runners = [order[g][1] for g in order if len(order[g]) >= 2]
    thirds = [order[g][2] for g in order if len(order[g]) >= 3]

    def score(t):
        return (exp_pts[t], elo.get(t, config.ELO_INITIAL))

    best_thirds = sorted(thirds, key=score, reverse=True)[:8]

    # תווית מקור לכל מעפילה (מאיזה בית ובאיזה מקום)
    origins: dict[str, str] = {}
    for g in order:
        if len(order[g]) >= 1:
            origins[order[g][0]] = f"מנצחת בית {g}"
        if len(order[g]) >= 2:
            origins[order[g][1]] = f"סגנית בית {g}"
    third_group = {order[g][2]: g for g in order if len(order[g]) >= 3}
    for t in best_thirds:
        origins[t] = f"שלישית בית {third_group[t]}"

    # זריעה: מנצחות (tier 3) מעל סגניות (2) מעל שלישיות (1); בתוך כל רמה לפי ניקוד
    pool = ([(t, 3) for t in winners] + [(t, 2) for t in runners]
            + [(t, 1) for t in best_thirds])
    pool.sort(key=lambda ts: (ts[1], *score(ts[0])), reverse=True)
    seeded = [t for t, _ in pool]

    pairs = bracket.build_r32(seeded)

    rounds = []
    champion = None
    ni = 0
    while pairs:
        matches, advancing = [], []
        for a, b in pairs:
            p = model.predict(a, b, neutral=True)
            denom = p.p_home + p.p_away
            ph = (p.p_home / denom) if denom > 0 else 0.5
            winner = a if p.p_home >= p.p_away else b
            match = {"home": a, "away": b, "winner": winner,
                     "prob": round(max(ph, 1 - ph) * 100)}
            if ni == 0:   # שלב הכניסה - מוסיפים תווית מקור
                match["home_from"] = origins.get(a, "")
                match["away_from"] = origins.get(b, "")
            matches.append(match)
            advancing.append(winner)
        name = ROUND_NAMES[ni] if ni < len(ROUND_NAMES) else f"שלב {len(pairs)}"
        rounds.append({"name": name, "matches": matches})
        ni += 1
        if len(advancing) == 1:
            champion = advancing[0]
            break
        pairs = [(advancing[i], advancing[i + 1]) for i in range(0, len(advancing), 2)]

    return rounds, champion
