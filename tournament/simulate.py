"""
סימולציית Monte-Carlo של שארית הטורניר.

לכל הרצה: מגריל תוצאות למשחקים שטרם שוחקו (מדגימה מתוך מטריצת ה-Poisson),
מחשב טבלאות, קובע מעפילים ובונה בראקט, ומשחק את הנוקאאוט עד אלוף.
צבירה על אלפי הרצות -> הסתברויות התקדמות וזכייה לכל נבחרת.

ביצועים: מטריצות התוצאות נשמרות ב-cache לכל זוג נבחרות (דטרמיניסטי),
כך שאלפי הרצות מהירות.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from tournament import bracket
from tournament.standings import compute_all


class MatchCache:
    """שומר מטריצת תוצאות + נתוני סבירות לכל זוג נבחרות."""

    def __init__(self, model, neutral: bool = True):
        self.model = model
        self.neutral = neutral
        self._mat = {}     # (home,away) -> (cumsum, n)
        self._adv = {}     # (home,away) -> (p_home, p_draw, p_away)

    def _matrix(self, home, away):
        key = (home, away)
        if key not in self._mat:
            lam_h, lam_a = self.model.expected_goals(home, away, self.neutral)
            m = self.model.score_matrix(lam_h, lam_a)
            self._mat[key] = (np.cumsum(m.ravel()), m.shape[0])
            p_home = float(np.tril(m, -1).sum())
            p_away = float(np.triu(m, 1).sum())
            self._adv[key] = (p_home, float(np.trace(m)), p_away)
        return self._mat[key]

    def sample_score(self, home, away, rng) -> tuple[int, int]:
        cumsum, n = self._matrix(home, away)
        idx = int(np.searchsorted(cumsum, rng.random()))
        return divmod(idx, n)

    def knockout_play(self, home, away, rng) -> tuple[str, int, int]:
        """מחזיר (מנצח, שערי בית, שערי חוץ). תיקו -> פנדלים."""
        self._matrix(home, away)
        hs, as_ = self.sample_score(home, away, rng)
        if hs > as_:
            return home, hs, as_
        if as_ > hs:
            return away, hs, as_
        # תיקו -> פנדלים, לפי יחס סיכויי הניצחון (השערים נספרים לתוצאה)
        p_home, _, p_away = self._adv[(home, away)]
        denom = p_home + p_away
        winner = home if rng.random() < (p_home / denom if denom > 0 else 0.5) else away
        return winner, hs, as_


def simulate(model, group_fixtures, team_groups, n_runs=10000, seed=42, neutral=True):
    """
    group_fixtures: רשימת dict {home, away, hs, as, played}.
    מחזיר: {team: {advance, round16, quarter, semi, final, winner}} כהסתברויות.
    """
    rng = np.random.default_rng(seed)
    cache = MatchCache(model, neutral=neutral)
    counts = defaultdict(lambda: defaultdict(int))
    goals_sum = defaultdict(float)   # סך השערים שכל קבוצה כובשת בטורניר (לאורך ההרצות)

    played = [f for f in group_fixtures if f.get("played")]
    pending = [f for f in group_fixtures if not f.get("played")]

    for _ in range(n_runs):
        results = [{"home": f["home"], "away": f["away"], "hs": f["hs"], "as": f["as"]}
                   for f in played]
        for f in pending:
            hs, as_ = cache.sample_score(f["home"], f["away"], rng)
            results.append({"home": f["home"], "away": f["away"], "hs": hs, "as": as_})

        # שערי שלב הבתים
        for r in results:
            goals_sum[r["home"]] += r["hs"]
            goals_sum[r["away"]] += r["as"]

        standings = compute_all(results, team_groups)
        quals = bracket.qualifiers(standings)
        seeded = bracket.seed_qualifiers(quals, standings)
        pairs = bracket.build_r32(seeded)

        for t in seeded:
            counts[t]["advance"] += 1

        round_keys = ["round16", "quarter", "semi", "final", "winner"]
        ki = 0
        while len(pairs) >= 1:
            winners = []
            for a, b in pairs:
                w, hs, as_ = cache.knockout_play(a, b, rng)
                goals_sum[a] += hs
                goals_sum[b] += as_
                winners.append(w)
            for w in winners:
                counts[w][round_keys[ki]] += 1
            ki += 1
            if len(winners) == 1:
                break
            pairs = [(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)]

    return {
        team: {**{k: c[k] / n_runs for k in
                  ("advance", "round16", "quarter", "semi", "final", "winner")},
               "exp_goals": goals_sum[team] / n_runs}
        for team, c in counts.items()
    }


# --- עזר לקריאת משחקי הבתים מ-DB ---
def group_fixtures_from_db(conn, season: int = 2026) -> list[dict]:
    rows = conn.execute(
        "SELECT h.name AS home, a.name AS away, f.home_goals AS hs, "
        "f.away_goals AS as_ FROM fixtures f "
        "JOIN teams h ON f.home_team_id = h.id "
        "JOIN teams a ON f.away_team_id = a.id "
        "WHERE f.season = ? AND f.grp IS NOT NULL",
        (season,),
    ).fetchall()
    return [
        {"home": r["home"], "away": r["away"], "hs": r["hs"], "as": r["as_"],
         "played": r["hs"] is not None}
        for r in rows
    ]
