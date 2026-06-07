"""
דגלי מדינות לנבחרות המונדיאל — כתמונות אמיתיות (flagcdn.com, חינמי).

חשוב: Windows לא מציג אמוג'י דגלים של מדינות, לכן משתמשים בתמונות PNG
לפי קוד ISO. עובד בכל מערכת הפעלה ובכל דפדפן.
"""
from __future__ import annotations

TEAM_ISO2 = {
    "Mexico": "mx", "South Africa": "za", "South Korea": "kr", "Czech Republic": "cz",
    "Canada": "ca", "Bosnia & Herzegovina": "ba", "Qatar": "qa", "Switzerland": "ch",
    "Brazil": "br", "Morocco": "ma", "Haiti": "ht",
    "USA": "us", "Paraguay": "py", "Australia": "au", "Turkey": "tr",
    "Germany": "de", "Curaçao": "cw", "Ivory Coast": "ci", "Ecuador": "ec",
    "Netherlands": "nl", "Japan": "jp", "Sweden": "se", "Tunisia": "tn",
    "Belgium": "be", "Egypt": "eg", "Iran": "ir", "New Zealand": "nz",
    "Spain": "es", "Cape Verde": "cv", "Saudi Arabia": "sa", "Uruguay": "uy",
    "France": "fr", "Senegal": "sn", "Iraq": "iq", "Norway": "no",
    "Argentina": "ar", "Algeria": "dz", "Austria": "at", "Jordan": "jo",
    "Portugal": "pt", "DR Congo": "cd", "Uzbekistan": "uz", "Colombia": "co",
    "Croatia": "hr", "Ghana": "gh", "Panama": "pa",
    # דגלי תת-מדינה (נתמכים ב-flagcdn)
    "England": "gb-eng", "Scotland": "gb-sct",
}


def flag_code(name: str) -> str:
    return TEAM_ISO2.get(name, "")


def flag_url(name: str, width: int = 40) -> str:
    """כתובת תמונת דגל (ריק אם לא ידוע)."""
    code = flag_code(name)
    return f"https://flagcdn.com/w{width}/{code}.png" if code else ""


def img(name: str, height: int = 14) -> str:
    """תג HTML של תמונת דגל קטנה, לשיבוץ בתוך markdown."""
    url = flag_url(name)
    if not url:
        return ""
    return (f"<img src='{url}' style='height:{height}px;border-radius:2px;"
            f"vertical-align:middle;margin-left:5px'>")


def name_html(name: str, height: int = 14) -> str:
    """דגל (כתמונה) + שם הנבחרת, ל-HTML."""
    tag = img(name, height)
    return f"{tag} {name}" if tag else name
