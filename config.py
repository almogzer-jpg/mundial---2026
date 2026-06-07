"""
הגדרות מרכזיות למערכת חיזוי המונדיאל.
כל הקבועים שמשמשים מודולים אחרים מרוכזים כאן.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# טען משתני סביבה מקובץ .env (אם קיים)
load_dotenv()

# --- נתיבים ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "mundial.db"

DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# --- API-Football ---
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
API_FOOTBALL_PROVIDER = os.getenv("API_FOOTBALL_PROVIDER", "apisports").lower()

# כתובות הבסיס משתנות לפי ספק
if API_FOOTBALL_PROVIDER == "rapidapi":
    API_BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
    API_AUTH_HEADER = "x-rapidapi-key"
    API_EXTRA_HEADERS = {"x-rapidapi-host": "api-football-v1.p.rapidapi.com"}
else:  # apisports (ישיר)
    API_BASE_URL = "https://v3.football.api-sports.io"
    API_AUTH_HEADER = "x-apisports-key"
    API_EXTRA_HEADERS = {}

# --- מזהי הטורניר ב-API-Football ---
WORLD_CUP_LEAGUE_ID = 1   # מזהה גביע העולם במערכת API-Football
SEASON = 2026             # עונת מונדיאל 2026

# --- מגבלות מסלול Free (להגנה מפני חריגה) ---
RATE_LIMIT_PER_MINUTE = 10
RATE_LIMIT_PER_DAY = 100

# --- פרמטרי מודל Elo ---
ELO_INITIAL = 1500.0          # דירוג פתיחה לנבחרת חדשה
ELO_K_MAX = 60.0              # K מרבי (מונדיאל נוקאאוט); סוגים אחרים = חלק ממנו
ELO_HOME_ADVANTAGE = 100.0    # בונוס למארחת (0 במגרש ניטרלי)

# --- פרמטר עדכניות (דעיכה מעריכית) — משמש את מודל ה-Poisson ---
# משקל = 0.5 ^ (גיל_בימים / מחצית-חיים). 365 ≈ מחצית כל שנה. יכוייל ב-Backtest.
RECENCY_HALF_LIFE_DAYS = 365

# --- פרמטרי מודל Poisson / Dixon-Coles (מכוילים ב-Backtest על 2010-2022) ---
DC_RHO = 0.0              # תיקון Dixon-Coles לתוצאות נמוכות (כיול: 0.0)
ELO_BLEND_BETA = 0.4      # 1=רק התקפה/הגנה, 0=רק Elo (כיול: 0.4)
ELO_TO_GOALS = 0.005      # המרת פער Elo לעליונות שערים (כיול: 0.005)
MAX_GOALS = 8             # גודל מטריצת התוצאות (0..8 לכל צד)
MONTE_CARLO_RUNS = 5000   # מספר הרצות סימולציית הטורניר

# --- התחשבות בפציעות (מוריד את חוזק הקבוצה) ---
INJURY_KEY_PENALTY = 0.10     # פגיעה לכל שחקן-מפתח פצוע
INJURY_MINOR_PENALTY = 0.02   # פגיעה לכל שחקן אחר פצוע
INJURY_MAX_PENALTY = 0.30     # תקרת הפגיעה לקבוצה
INJURY_ELO_SCALE = 200.0      # כמה נקודות Elo יורדות בפגיעה מלאה

# ספי רמת ביטחון (לפי ההסתברות הגבוהה מבין נצ'/תיקו/הפ')
CONFIDENCE_HIGH = 0.55
CONFIDENCE_MEDIUM = 0.42

# --- תצוגת תאריכים (תקן ישראלי) ---
DATE_DISPLAY_FORMAT = "%d/%m/%Y"        # DD/MM/YYYY
DATETIME_DISPLAY_FORMAT = "%d/%m/%Y %H:%M"

# --- גרסת מודל החיזוי (נשמר עם כל תחזית) ---
MODEL_VERSION = "0.1.0"
