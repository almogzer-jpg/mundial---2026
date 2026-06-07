"""שכבת ספקי נתונים — ממשק אחיד מעל מקורות שונים (פתוח / ידני / API עתידי)."""
from ingestion.providers.base import (
    DataProvider,
    Fixture,
    HistoricalMatch,
    WorldCupTeam,
)

__all__ = ["DataProvider", "Fixture", "HistoricalMatch", "WorldCupTeam"]
