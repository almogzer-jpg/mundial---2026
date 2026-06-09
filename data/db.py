"""
שכבת מסד הנתונים (SQLite).
יוצרת את כל הטבלאות ומספקת חיבור משותף.
הסכימה תואמת לסעיף 3 באפיון: נבחרות, שחקנים, סגלים, משחקים,
אירועים, הרכבים, פציעות, טבלאות, היסטוריית Elo, תחזיות, סימולציות ולוג קליטה.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import config

# --- הגדרת כל הטבלאות ---
SCHEMA = """
-- נבחרות (מפתח פנימי משלנו; מזהה חיצוני נשמר בנפרד לחיבור API עתידי)
CREATE TABLE IF NOT EXISTS teams (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,       -- שם הנבחרת (מפתח טבעי)
    code        TEXT,                       -- קוד 3 אותיות (FIFA)
    grp         TEXT,                       -- בית (A-L)
    fifa_rank   INTEGER,
    elo         REAL,                       -- דירוג Elo נוכחי
    ext_api_football_id INTEGER,            -- מיפוי עתידי ל-API-Football
    logo        TEXT
);

-- תוצאות נבחרות היסטוריות (מקור: martj42/international_results)
-- משמשות לחישוב Elo, חוזקי התקפה/הגנה ו-Backtest. מזוהות לפי שם.
CREATE TABLE IF NOT EXISTS historical_matches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT,                       -- ISO YYYY-MM-DD
    home_team   TEXT,
    away_team   TEXT,
    home_score  INTEGER,
    away_score  INTEGER,
    tournament  TEXT,                       -- "FIFA World Cup", "Friendly" ...
    neutral     INTEGER,                    -- 1=מגרש ניטרלי
    UNIQUE (date, home_team, away_team)
);

-- שחקנים
CREATE TABLE IF NOT EXISTS players (
    id          INTEGER PRIMARY KEY,
    team_id     INTEGER REFERENCES teams(id),
    name        TEXT NOT NULL,
    position    TEXT,
    age         INTEGER,
    photo       TEXT
);

-- סגל לפי עונה (מי שייך לאיזו נבחרת)
CREATE TABLE IF NOT EXISTS squads (
    team_id     INTEGER REFERENCES teams(id),
    player_id   INTEGER REFERENCES players(id),
    season      INTEGER,
    PRIMARY KEY (team_id, player_id, season)
);

-- משחקים
CREATE TABLE IF NOT EXISTS fixtures (
    id            INTEGER PRIMARY KEY,
    season        INTEGER,
    round         TEXT,                     -- "Group Stage - 1", "Round of 16" ...
    grp           TEXT,
    date_utc      TEXT,                     -- ISO-8601 UTC
    venue         TEXT,
    city          TEXT,
    status        TEXT,                     -- NS / FT / LIVE ...
    home_team_id  INTEGER REFERENCES teams(id),
    away_team_id  INTEGER REFERENCES teams(id),
    home_goals    INTEGER,
    away_goals    INTEGER,
    is_neutral    INTEGER DEFAULT 1         -- במונדיאל רוב המגרשים ניטרליים
);

-- מפתח טבעי למשחק (לאפשר upsert ושמירת מזהה יציב עבור תחזיות)
CREATE UNIQUE INDEX IF NOT EXISTS idx_fixtures_natural
    ON fixtures (season, home_team_id, away_team_id);

-- אירועים במשחק (שערים, כרטיסים) -> נגזור מהם הרחקות
CREATE TABLE IF NOT EXISTS fixture_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id  INTEGER REFERENCES fixtures(id),
    minute      INTEGER,
    type        TEXT,                       -- Goal / Card / subst
    detail      TEXT,                       -- Yellow Card / Red Card ...
    team_id     INTEGER REFERENCES teams(id),
    player_id   INTEGER REFERENCES players(id)
);

-- הרכבים בפועל
CREATE TABLE IF NOT EXISTS fixture_lineups (
    fixture_id  INTEGER REFERENCES fixtures(id),
    team_id     INTEGER REFERENCES teams(id),
    player_id   INTEGER REFERENCES players(id),
    is_starter  INTEGER,                    -- 1=הרכב, 0=ספסל
    position    TEXT,
    PRIMARY KEY (fixture_id, player_id)
);

-- פציעות / נעדרים
CREATE TABLE IF NOT EXISTS injuries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER REFERENCES players(id),
    team_id     INTEGER REFERENCES teams(id),
    player_name TEXT,                       -- שם השחקן (מ-API/ידני)
    type        TEXT,                       -- Injury / Suspended ...
    reason      TEXT,
    status      TEXT,
    date        TEXT
);

-- סגל נוכחי (מויקיפדיה) — בסיס ל-Current Team Strength
CREATE TABLE IF NOT EXISTS squad_players (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     INTEGER REFERENCES teams(id),
    name        TEXT,
    pos         TEXT,
    age         INTEGER,
    caps        INTEGER,
    goals       INTEGER,
    club        TEXT,
    clubnat     TEXT,
    rating      REAL
);

-- טבלאות בתים
CREATE TABLE IF NOT EXISTS standings (
    season      INTEGER,
    grp         TEXT,
    team_id     INTEGER REFERENCES teams(id),
    rank        INTEGER,
    played      INTEGER,
    win         INTEGER,
    draw        INTEGER,
    loss        INTEGER,
    goals_for   INTEGER,
    goals_against INTEGER,
    goal_diff   INTEGER,
    points      INTEGER,
    PRIMARY KEY (season, grp, team_id)
);

-- היסטוריית Elo (snapshot אחרי כל משחק - לא נמחק)
CREATE TABLE IF NOT EXISTS elo_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     INTEGER REFERENCES teams(id),
    date        TEXT,
    rating      REAL,
    change      REAL,
    fixture_id  INTEGER REFERENCES fixtures(id)
);

-- תחזיות (snapshot לכל משחק - לכיול ומדידת דיוק בדיעבד)
CREATE TABLE IF NOT EXISTS predictions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id    INTEGER REFERENCES fixtures(id),
    created_at    TEXT,
    p_home        REAL,
    p_draw        REAL,
    p_away        REAL,
    exp_home_goals REAL,
    exp_away_goals REAL,
    likely_score  TEXT,                     -- "2-1" (הסבירה ביותר)
    top_scores    TEXT,                     -- JSON: 5 התוצאות המובילות + הסתברות
    confidence    TEXT,                     -- low / medium / high
    model_version TEXT
);

-- תוצאות סימולציית הטורניר (Monte-Carlo)
CREATE TABLE IF NOT EXISTS tournament_sim (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at        TEXT,
    team_id       INTEGER REFERENCES teams(id),
    p_advance     REAL,    -- עולה מהבית
    p_win_group   REAL,
    p_round16     REAL,
    p_quarter     REAL,
    p_semi        REAL,
    p_final       REAL,
    p_winner      REAL
);

-- לוג קליטה / cache (לניהול rate-limit ומניעת בקשות כפולות)
CREATE TABLE IF NOT EXISTS ingestion_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint    TEXT,
    params      TEXT,
    fetched_at  TEXT,
    status      TEXT,
    rows        INTEGER
);
"""


def get_connection(db_path: Path | str = None) -> sqlite3.Connection:
    """מחזיר חיבור ל-SQLite עם הגדרות נוחות."""
    path = str(db_path or config.DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row          # גישה לעמודות לפי שם
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection(db_path: Path | str = None):
    """Context manager שסוגר את החיבור אוטומטית."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate(conn) -> None:
    """מיגרציות קטנות ל-DB קיים (הוספת עמודות חסרות)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(injuries)").fetchall()}
    if "player_name" not in cols:
        conn.execute("ALTER TABLE injuries ADD COLUMN player_name TEXT")
    # עמודות כוח-סגל על teams
    tcols = {r[1] for r in conn.execute("PRAGMA table_info(teams)").fetchall()}
    for col in ("ssi", "squad_adj", "squad_n"):
        if col not in tcols:
            conn.execute(f"ALTER TABLE teams ADD COLUMN {col} REAL")
    scols = {r[1] for r in conn.execute("PRAGMA table_info(tournament_sim)").fetchall()}
    if "exp_goals" not in scols:
        conn.execute("ALTER TABLE tournament_sim ADD COLUMN exp_goals REAL")


def init_db(db_path: Path | str = None) -> None:
    """יוצר את כל הטבלאות (idempotent - בטוח להריץ שוב)."""
    with connection(db_path) as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


if __name__ == "__main__":
    init_db()
    print(f"מסד הנתונים אותחל בהצלחה: {config.DB_PATH}")
