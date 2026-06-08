"""
כוח סגל נוכחי (Current Team Strength) — מבוסס איכות המועדונים של הסגל.

רעיון: שחקן שמשחק בליגה בכירה / מועדון עילית מעיד על כוח עכשווי
שה-Elo ההיסטורי עלול לפספס. מחשבים לכל שחקן "דירוג מועדון" לפי
מדינת הליגה (clubnat) + בונוס למועדוני צמרת, מסכמים לאינדקס סגל (SSI),
ומתרגמים לתוספת/הפחתה בסקאלת Elo (יחסית לממוצע 48 הנבחרות).

חינמי לחלוטין — נשען רק על נתוני ויקיפדיה (clubnat), בלי API חיצוני.
"""
from __future__ import annotations

import statistics

import config

# רמת ליגה לפי קוד מדינת המועדון (FIFA/IOC)
LEAGUE_STRENGTH = {
    # צמרת אירופה
    "ENG": 100, "ESP": 100, "ITA": 96, "GER": 95, "FRA": 90,
    # גבוהה
    "POR": 82, "NED": 80, "BEL": 74, "TUR": 72,
    # עליונה-בינונית
    "KSA": 70, "BRA": 70, "ARG": 68, "USA": 64, "MEX": 64,
    "SCO": 62, "GRE": 60, "AUT": 60, "SUI": 60, "UKR": 60, "RUS": 60,
    # בינונית
    "CRO": 56, "CZE": 56, "DEN": 56, "NOR": 56, "SWE": 56, "POL": 54,
    "JPN": 56, "KOR": 54, "QAT": 52, "UAE": 50, "EGY": 50,
}
DEFAULT_LEAGUE = 46

# מועדוני עילית (התאמה לפי תת-מחרוזת בשם המועדון)
ELITE_CLUBS = {
    "real madrid": 30, "barcelona": 28, "manchester city": 30, "liverpool": 26,
    "arsenal": 26, "bayern": 28, "paris saint-germain": 26, "inter milan": 22,
    "inter ": 22, "milan": 20, "juventus": 20, "atlético madrid": 22,
    "atletico madrid": 22, "chelsea": 22, "manchester united": 20, "tottenham": 18,
    "napoli": 18, "borussia dortmund": 18, "leverkusen": 18, "atalanta": 16,
    "newcastle": 16, "aston villa": 14, "benfica": 14, "porto": 12, "sporting": 12,
    "ajax": 12, "psv": 12, "feyenoord": 10, "marseille": 12, "roma": 14, "lazio": 12,
    "real sociedad": 12, "villarreal": 12, "athletic": 12, "bologna": 12,
}


def player_rating(clubnat: str, club: str) -> float:
    base = LEAGUE_STRENGTH.get((clubnat or "").upper(), DEFAULT_LEAGUE)
    c = (club or "").lower()
    bonus = max((b for sub, b in ELITE_CLUBS.items() if sub in c), default=0)
    return base + bonus


def squad_index(players) -> dict:
    """אינדקס סגל גולמי + נתוני רקע. שקלול לפי קאפים (קירוב ל'מי שחקן הרכב')."""
    if not players:
        return {"ssi": DEFAULT_LEAGUE, "avg_age": 0, "avg_caps": 0, "n": 0}
    num = den = 0.0
    for p in players:
        w = min(p.caps, 40) + 5          # ותיקים שוקלים יותר, כולם נספרים
        num += w * player_rating(p.clubnat, p.club)
        den += w
    ssi = num / den if den else DEFAULT_LEAGUE
    return {
        "ssi": ssi,
        "avg_age": statistics.mean(p.age for p in players if p.age) if players else 0,
        "avg_caps": statistics.mean(p.caps for p in players),
        "n": len(players),
    }


def compute_adjustments(squads_by_team: dict[str, list]) -> dict[str, dict]:
    """
    מחזיר {team: {ssi, squad_adj, avg_age, avg_caps, n}}.
    squad_adj = z-score(SSI) × ELO_PER_SIGMA  (תוספת Elo גולמית, לפני CTS_WEIGHT).
    """
    idx = {t: squad_index(ps) for t, ps in squads_by_team.items()}
    ssis = [v["ssi"] for v in idx.values()]
    mean = statistics.mean(ssis) if ssis else DEFAULT_LEAGUE
    std = statistics.pstdev(ssis) if len(ssis) > 1 else 1.0
    std = std or 1.0
    out = {}
    for t, v in idx.items():
        z = (v["ssi"] - mean) / std
        out[t] = {**v, "squad_adj": round(z * config.CTS_ELO_PER_SIGMA, 1)}
    return out
