"""
תחזית מלך שערים (Golden Boot) — מבוסס נתונים אמיתיים.

הגישה (הגיונית ומבוססת-דאטה, לא רשימה מקודדת):
  1. מהסימולציה — כמה שערים כל קבוצה צפויה לכבוש בטורניר (כולל כמה רחוק תגיע).
  2. מהסגל האמיתי (ויקיפדיה) — מחלקים את שערי הקבוצה בין השחקנים לפי
     "נטיית הבקעה": עמדה (חלוץ > קשר > מגן) × שערי הנבחרת בקריירה של השחקן.
  3. שערים צפויים לשחקן = שערי הקבוצה × נתח השחקן.

כך מוצגים רק שחקנים שבאמת בסגל, מדורגים לפי הרקורד האמיתי שלהם.
"""
from __future__ import annotations

# משקל עמדה לנטיית הבקעת שערים
POS_WEIGHT = {"FW": 1.0, "MF": 0.55, "DF": 0.15, "GK": 0.0}


def _propensity(player: dict) -> float:
    """נטיית הבקעה: עמדה × (שערי נבחרת + רצפה קטנה לחלוצים)."""
    pos = (player.get("pos") or "").upper()[:2]
    pw = POS_WEIGHT.get(pos, 0.3)
    goals = player.get("goals") or 0
    # רצפה קטנה לחלוצים צעירים שעוד לא צברו שערים
    base = goals + (0.8 if pos == "FW" else 0.0)
    return pw * base


def golden_boot(team_stats: dict[str, dict],
                squads_by_team: dict[str, list[dict]],
                top_n: int = 15) -> list[dict]:
    """
    team_stats: {team: {'exp_goals': X, ...}} מהסימולציה.
    squads_by_team: {team: [{name, pos, goals, caps, club}, ...]}.
    מחזיר רשימה ממוינת: {player, team, club, exp_goals}.
    """
    out: list[dict] = []
    for team, players in squads_by_team.items():
        stats = team_stats.get(team)
        if not stats or not players:
            continue
        team_goals = stats.get("exp_goals", 0.0)
        weighted = [(p, _propensity(p)) for p in players]
        total = sum(w for _, w in weighted)
        if total <= 0:
            continue
        for p, w in weighted:
            if w <= 0:
                continue
            xg = team_goals * (w / total)
            if xg >= 0.4:                     # רק מועמדים בעלי משמעות
                out.append({
                    "player": p["name"], "team": team,
                    "club": p.get("club", ""), "goals_nt": p.get("goals", 0),
                    "exp_goals": round(xg, 2),
                })
    out.sort(key=lambda d: d["exp_goals"], reverse=True)
    return out[:top_n]
