"""
תחזית מלך שערים (Golden Boot).

הגישה: מהסימולציה מקבלים כמה שערים כל קבוצה צפויה לכבוש לאורך הטורניר
(כולל כמה רחוק היא מגיעה). מייחסים נתח מהשערים לחלוץ המוביל של הקבוצה:
    שערים צפויים לשחקן = שערי הקבוצה × נתח השחקן

הערה כנה: זוהי הערכה ספקולטיבית. הרשימה והנתחים ניתנים לעריכה כאן.
אם API-Football מחובר ויש שערים בפועל — אפשר בעתיד לשלב אותם.
"""
from __future__ import annotations

# נבחרת -> (שם החלוץ המוביל, נתח השערים שלו מתוך שערי הקבוצה)
TOP_SCORERS: dict[str, tuple[str, float]] = {
    "France": ("Kylian Mbappé", 0.38),
    "England": ("Harry Kane", 0.34),
    "Argentina": ("Lautaro Martínez", 0.27),
    "Brazil": ("Vinícius Júnior", 0.27),
    "Spain": ("Lamine Yamal", 0.22),
    "Portugal": ("Cristiano Ronaldo", 0.28),
    "Germany": ("Kai Havertz", 0.24),
    "Netherlands": ("Memphis Depay", 0.26),
    "Belgium": ("Romelu Lukaku", 0.34),
    "Norway": ("Erling Haaland", 0.45),
    "Uruguay": ("Darwin Núñez", 0.32),
    "Colombia": ("Luis Díaz", 0.30),
    "Morocco": ("Youssef En-Nesyri", 0.28),
    "Egypt": ("Mohamed Salah", 0.42),
    "Senegal": ("Sadio Mané", 0.30),
    "Japan": ("Ayase Ueda", 0.24),
    "Croatia": ("Andrej Kramarić", 0.26),
    "Mexico": ("Raúl Jiménez", 0.30),
    "USA": ("Christian Pulisic", 0.28),
    "Switzerland": ("Breel Embolo", 0.28),
    "Ecuador": ("Enner Valencia", 0.34),
    "Australia": ("Mitchell Duke", 0.28),
}


def golden_boot(team_stats: dict[str, dict]) -> list[dict]:
    """
    team_stats: פלט הסימולציה {team: {..., 'exp_goals': X}}.
    מחזיר רשימה ממוינת של מועמדים: {player, team, exp_goals}.
    """
    out = []
    for team, (player, share) in TOP_SCORERS.items():
        stats = team_stats.get(team)
        if not stats:
            continue
        exp = stats.get("exp_goals", 0.0) * share
        out.append({"player": player, "team": team, "exp_goals": round(exp, 2)})
    out.sort(key=lambda d: d["exp_goals"], reverse=True)
    return out
