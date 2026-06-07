"""
נרמול שמות נבחרות בין מקורות שונים.

מקורות שונים מאייתים את אותה נבחרת בצורה שונה (USA / United States).
כאן ממירים הכל ל"שם קנוני" אחד (זה של openfootball, שממנו נגזרים הבתים),
כדי ששיוך הבתים, הלוח וההיסטוריה יתחברו לאותה נבחרת.

הערה: נרמול של ישויות היסטוריות (West Germany→Germany וכד') הוא
החלטה מודלית שתטופל במפורש בשלב ה-Elo, ולא כאן.
"""
from __future__ import annotations

# שם במקור  ->  שם קנוני (openfootball)
TEAM_ALIASES: dict[str, str] = {
    # martj42
    "United States": "USA",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    # API-Football (שמות FIFA רשמיים) -> קנוני
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
    "Cabo Verde": "Cape Verde",
    "Congo DR": "DR Congo",
    "Côte d'Ivoire": "Ivory Coast",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "Curacao": "Curaçao",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
}


def canonical(name: str) -> str:
    name = name.strip()
    return TEAM_ALIASES.get(name, name)
