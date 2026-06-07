"""
טבלאות בתים + שוברי-שוויון של פיפ"א.

סדר הדירוג (מונדיאל):
  1. נקודות בכל משחקי הבית
  2. הפרש שערים כללי
  3. שערי זכות כללי
  ואם עדיין שוויון בין קבוצות:
  4. נקודות במשחקים ביניהן (head-to-head)
  5. הפרש שערים ביניהן
  6. שערי זכות ביניהן
  7. הגרלה (כאן: סדר אלפביתי יציב)

הליבה פועלת על רשימת תוצאות — כך שגם סימולציית Monte-Carlo משתמשת בה.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

WIN_POINTS, DRAW_POINTS = 3, 1


@dataclass
class Row:
    team: str
    played: int = 0
    win: int = 0
    draw: int = 0
    loss: int = 0
    gf: int = 0
    ga: int = 0

    @property
    def gd(self) -> int:
        return self.gf - self.ga

    @property
    def points(self) -> int:
        return self.win * WIN_POINTS + self.draw * DRAW_POINTS


def _accumulate(rows: dict[str, Row], home, away, hs, as_) -> None:
    rh, ra = rows[home], rows[away]
    rh.played += 1
    ra.played += 1
    rh.gf += hs; rh.ga += as_
    ra.gf += as_; ra.ga += hs
    if hs > as_:
        rh.win += 1; ra.loss += 1
    elif hs < as_:
        ra.win += 1; rh.loss += 1
    else:
        rh.draw += 1; ra.draw += 1


def _h2h_order(tied: list[str], results) -> list[str]:
    """מדרג תת-קבוצה תקועה לפי משחקיהן ההדדיים."""
    sub = {t: Row(t) for t in tied}
    tied_set = set(tied)
    for r in results:
        if r["home"] in tied_set and r["away"] in tied_set:
            _accumulate(sub, r["home"], r["away"], r["hs"], r["as"])
    return sorted(
        tied,
        key=lambda t: (sub[t].points, sub[t].gd, sub[t].gf, t),
        reverse=True,
    )


def compute_group(results, teams: list[str]) -> list[Row]:
    """מחזיר טבלת בית ממוינת (results = רק משחקי הבית שהושלמו)."""
    rows = {t: Row(t) for t in teams}
    for r in results:
        if r["home"] in rows and r["away"] in rows:
            _accumulate(rows, r["home"], r["away"], r["hs"], r["as"])

    # מיון ראשוני: נק' -> הפרש -> זכות
    ordered = sorted(
        teams, key=lambda t: (rows[t].points, rows[t].gd, rows[t].gf), reverse=True
    )
    # פירוק תיקו על שלושת הקריטריונים באמצעות head-to-head
    final: list[str] = []
    i = 0
    while i < len(ordered):
        j = i + 1
        key_i = (rows[ordered[i]].points, rows[ordered[i]].gd, rows[ordered[i]].gf)
        while j < len(ordered) and (
            rows[ordered[j]].points, rows[ordered[j]].gd, rows[ordered[j]].gf
        ) == key_i:
            j += 1
        block = ordered[i:j]
        final.extend(_h2h_order(block, results) if len(block) > 1 else block)
        i = j
    return [rows[t] for t in final]


def compute_all(results, team_groups: dict[str, str]) -> dict[str, list[Row]]:
    """כל הבתים. team_groups: {team: group}."""
    groups = defaultdict(list)
    for team, g in team_groups.items():
        groups[g].append(team)
    by_group = defaultdict(list)
    for r in results:
        g = team_groups.get(r["home"])
        if g and team_groups.get(r["away"]) == g:
            by_group[g].append(r)
    return {
        g: compute_group(by_group.get(g, []), teams)
        for g, teams in sorted(groups.items())
    }


# --- עזר לקריאה מ-DB ---
def results_from_db(conn, season: int = 2026) -> list[dict]:
    rows = conn.execute(
        "SELECT h.name AS home, a.name AS away, f.home_goals AS hs, "
        "f.away_goals AS as_, f.grp FROM fixtures f "
        "JOIN teams h ON f.home_team_id = h.id "
        "JOIN teams a ON f.away_team_id = a.id "
        "WHERE f.season = ? AND f.home_goals IS NOT NULL AND f.grp IS NOT NULL",
        (season,),
    ).fetchall()
    return [{"home": r["home"], "away": r["away"], "hs": r["hs"], "as": r["as_"]} for r in rows]


def team_groups_from_db(conn) -> dict[str, str]:
    return {
        r["name"]: r["grp"]
        for r in conn.execute("SELECT name, grp FROM teams WHERE grp IS NOT NULL").fetchall()
    }
