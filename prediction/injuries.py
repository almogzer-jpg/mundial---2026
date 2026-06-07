"""
שכבת התחשבות בפציעות — ממירה רשימת פצועים ל"מקדם זמינות" לכל קבוצה.

זמינות = 1.0 (קבוצה מלאה) ויורדת לפי פצועים:
  • שחקן-מפתח פצוע  -> פגיעה גדולה (INJURY_KEY_PENALTY)
  • שחקן אחר פצוע   -> פגיעה קטנה  (INJURY_MINOR_PENALTY)
  הפגיעה הכוללת מוגבלת ב-INJURY_MAX_PENALTY.

המקדם משפיע במודל: מוריד את כוח ההתקפה ואת עליונות ה-Elo של הקבוצה.

הערה כנה: זוהי הערכה. "כמה שווה שחקן" אינו מדע מדויק — רשימת
שחקני-המפתח ניתנת לעריכה כאן לפי שיקול דעת.
"""
from __future__ import annotations

import unicodedata

import config


def _norm(s: str) -> str:
    """נרמול להשוואה: הסרת סימנים דיאקריטיים + אותיות קטנות."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


# שחקני-מפתח לכל נבחרת (התאמה לפי תת-מחרוזת, ללא רגישות לניקוד)
STAR_PLAYERS: dict[str, list[str]] = {
    "France": ["mbappe", "dembele", "tchouameni"],
    "England": ["bellingham", "kane", "saka", "foden"],
    "Spain": ["yamal", "rodri", "pedri"],
    "Argentina": ["messi", "lautaro", "alvarez"],
    "Brazil": ["vinicius", "rodrygo", "raphinha", "neymar"],
    "Portugal": ["ronaldo", "bruno fernandes", "leao"],
    "Germany": ["musiala", "wirtz", "kimmich"],
    "Netherlands": ["van dijk", "gakpo", "depay"],
    "Belgium": ["de bruyne", "lukaku", "doku"],
    "Croatia": ["modric"],
    "Morocco": ["hakimi", "ziyech", "amrabat"],
    "Norway": ["haaland", "odegaard"],
    "Uruguay": ["nunez", "valverde"],
    "Colombia": ["rodriguez", "diaz"],
    "Japan": ["mitoma", "kubo", "kamada"],
    "Senegal": ["mane", "koulibaly"],
}


def _is_key(team: str, player: str) -> bool:
    stars = STAR_PLAYERS.get(team, [])
    pn = _norm(player)
    return any(star in pn for star in stars)


def team_availability(team: str, injured_players: list[str]) -> float:
    """מקדם זמינות לקבוצה (0..1) לפי רשימת שמות פצועים."""
    penalty = 0.0
    for player in injured_players:
        penalty += (config.INJURY_KEY_PENALTY if _is_key(team, player)
                    else config.INJURY_MINOR_PENALTY)
    return 1.0 - min(config.INJURY_MAX_PENALTY, penalty)


def availability_map(injuries_by_team: dict[str, list[str]]) -> dict[str, float]:
    """{team: factor} לכל הקבוצות שיש להן פצועים."""
    return {team: team_availability(team, players)
            for team, players in injuries_by_team.items()}
