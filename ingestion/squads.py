"""
קליטת סגלי מונדיאל 2026 מויקיפדיה (חינמי, ללא מפתח).

מקור: הערך "2026 FIFA World Cup squads" — נקרא כ-wikitext דרך ה-API
של ויקיפדיה, ומנתחים את תבניות השחקנים ({{nat fs g player|...}}).
לכל שחקן: שם, עמדה, גיל, קאפים, שערים, מועדון, מדינת-מועדון.
שומר עותק מקומי (cache) לעבודה גם offline.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

import requests

import config
from ingestion.names import canonical

WIKI_API = "https://en.wikipedia.org/w/api.php"
PAGE = "2026 FIFA World Cup squads"
REF_DATE = (2026, 6, 11)   # מועד ייחוס לחישוב גיל (פתיחת הטורניר)


@dataclass
class SquadPlayer:
    name: str
    pos: str
    age: int
    caps: int
    goals: int
    club: str
    clubnat: str   # קוד מדינת המועדון (ENG/ESP/...)


def _fetch_wikitext(ttl: int = 86400) -> str:
    path = config.CACHE_DIR / "wc2026_squads.wikitext"
    if path.exists() and time.time() - path.stat().st_mtime < ttl:
        return path.read_text(encoding="utf-8")
    resp = requests.get(
        WIKI_API,
        params={"action": "parse", "page": PAGE, "prop": "wikitext",
                "format": "json", "formatversion": "2"},
        headers={"User-Agent": "MundialPredictor/1.0 (personal project)"},
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["parse"]["wikitext"]
    path.write_text(text, encoding="utf-8")
    return text


def _link_field(line: str, key: str) -> str:
    """
    מחלץ שדה שעשוי להכיל קישור ויקי עם '|' פנימי:
    name=[[A (disambig)|B]] -> B ;  club=[[A]] -> A ;  name=Plain -> Plain.
    """
    m = re.search(rf"\|\s*{key}\s*=\s*\[\[([^\]]+)\]\]", line)
    if m:
        return m.group(1).split("|")[-1].strip()
    m2 = re.search(rf"\|\s*{key}\s*=\s*([^|}}\n]+)", line)
    return m2.group(1).strip() if m2 else ""


def _age_from_template(line: str) -> int | None:
    m = re.search(r"birth date and age2\|(\d+)\|(\d+)\|(\d+)\|(\d+)\|(\d+)\|(\d+)", line)
    if not m:
        return None
    ry, rm, rd, by, bm, bd = (int(x) for x in m.groups())
    age = ry - by - (1 if (rm, rd) < (bm, bd) else 0)
    return age


def _field(line: str, key: str) -> str | None:
    m = re.search(rf"\|\s*{key}\s*=\s*([^|}}]+)", line)
    return m.group(1).strip() if m else None


def parse_squads() -> dict[str, list[SquadPlayer]]:
    """מחזיר {team קנוני: [SquadPlayer]}."""
    text = _fetch_wikitext()
    squads: dict[str, list[SquadPlayer]] = {}
    current: str | None = None
    for line in text.splitlines():
        header = re.match(r"^===\s*(.+?)\s*===\s*$", line)
        if header:
            current = canonical(header.group(1))
            squads.setdefault(current, [])
            continue
        if current and "nat fs" in line and "player" in line:
            name = _link_field(line, "name")
            if not name:
                continue
            squads[current].append(SquadPlayer(
                name=name,
                pos=(_field(line, "pos") or "").strip(),
                age=_age_from_template(line) or 0,
                caps=int(re.sub(r"\D", "", _field(line, "caps") or "0") or 0),
                goals=int(re.sub(r"\D", "", _field(line, "goals") or "0") or 0),
                club=_link_field(line, "club"),
                clubnat=(_field(line, "clubnat") or "").strip().upper()[:3],
            ))
    # רק נבחרות עם סגל אמיתי
    return {t: ps for t, ps in squads.items() if ps}


if __name__ == "__main__":
    sq = parse_squads()
    print(f"נבחרות עם סגל: {len(sq)}")
    total = sum(len(v) for v in sq.values())
    print(f"סך שחקנים: {total}")
