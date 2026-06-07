"""
ממשק ספק נתונים אחיד (DataProvider) + מבני נתונים מנורמלים.

זהו הלב של גמישות המערכת: כל מקור נתונים (פתוח / ידני / API עתידי)
מממש את אותו ממשק. הוספת מקור חדש = מחלקה חדשה בלבד, ללא שינוי
במודל החיזוי, בלוגיקת הטורניר, ב-UI או במבנה ה-DB.

ספק שאינו תומך בפעולה מסוימת פשוט מחזיר רשימה ריקה (ברירת מחדל),
כך שאפשר למזג כמה מקורות יחד.
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Optional


@dataclass
class HistoricalMatch:
    """תוצאת משחק נבחרות היסטורי (שהושלם)."""
    date: str               # YYYY-MM-DD
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    tournament: str
    neutral: bool


@dataclass
class WorldCupTeam:
    """נבחרת במונדיאל 2026 + שיוך לבית."""
    name: str
    group: str              # A-L
    code: Optional[str] = None


@dataclass
class Fixture:
    """משחק בטורניר (עתידי או שהושלם)."""
    date_utc: str
    home_team: str
    away_team: str
    round: str = "Group Stage"
    group: Optional[str] = None
    venue: Optional[str] = None
    city: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    status: str = "NS"      # NS=טרם החל, FT=הסתיים
    neutral: bool = True


class DataProvider(ABC):
    """
    ממשק בסיס. כל מימוש מחזיר נתונים מנורמלים.
    ברירת המחדל לכל פעולה: ריק — מימוש דורס רק את מה שהוא תומך בו.
    """

    name: str = "base"

    def is_available(self) -> bool:
        """האם המקור זמין כרגע (רשת/קובץ)."""
        return True

    # --- נתונים נתמכים בשלב 1 ---
    def get_historical_matches(self) -> list[HistoricalMatch]:
        return []

    def get_world_cup_teams(self) -> list[WorldCupTeam]:
        return []

    def get_fixtures(self) -> list[Fixture]:
        return []

    # --- ווים להרחבות עתידיות (פציעות/סגלים/הימורים) ---
    def get_injuries(self) -> list[dict]:
        return []

    def get_squads(self, team_name: str) -> list[dict]:
        return []

    def get_odds(self, home_team: str, away_team: str) -> Optional[dict]:
        return None
