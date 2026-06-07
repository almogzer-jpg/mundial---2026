"""
מנוע Elo לנבחרות — נוסחת World Football Elo.

  We = 1 / (1 + 10^(-(Δr + יתרון_בית)/400))
  r' = r + K · G · (תוצאה − We)

  K = חשיבות × ELO_K_MAX   (משחקי מונדיאל/נוקאאוט מזיזים יותר מידידות)
  G = מכפיל הפרש שערים      (ניצחון גדול מזיז יותר)
  יתרון בית = 0 במגרש ניטרלי

עדכניות אינה מיושמת כאן: ב-Elo היא מובנית (משחק חדש דורס ישן ברצף).
משקל העדכניות המעריכי מיושם במודל ה-Poisson (שלב 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import config
from ratings.weights import importance_weight


@dataclass
class EloEngine:
    initial: float = config.ELO_INITIAL
    k_max: float = config.ELO_K_MAX
    home_advantage: float = config.ELO_HOME_ADVANTAGE
    ratings: dict[str, float] = field(default_factory=dict)

    def get(self, team: str) -> float:
        return self.ratings.get(team, self.initial)

    @staticmethod
    def expected(r_home: float, r_away: float, home_adv: float) -> float:
        dr = r_home - r_away + home_adv
        return 1.0 / (1.0 + 10 ** (-dr / 400.0))

    @staticmethod
    def goal_multiplier(goal_diff: int) -> float:
        """מכפיל הפרש שערים (World Football Elo)."""
        d = abs(goal_diff)
        if d <= 1:
            return 1.0
        if d == 2:
            return 1.5
        return (11 + d) / 8.0

    def update_match(
        self,
        home: str,
        away: str,
        home_score: int,
        away_score: int,
        tournament: str,
        neutral: bool,
        round_name: str | None = None,
    ) -> tuple[float, float]:
        """מעדכן את דירוגי שתי הנבחרות לפי תוצאת משחק. מחזיר (Δבית, Δחוץ)."""
        r_home, r_away = self.get(home), self.get(away)
        home_adv = 0.0 if neutral else self.home_advantage

        we_home = self.expected(r_home, r_away, home_adv)
        if home_score > away_score:
            w_home = 1.0
        elif home_score < away_score:
            w_home = 0.0
        else:
            w_home = 0.5

        k = importance_weight(tournament, round_name) * self.k_max
        g = self.goal_multiplier(home_score - away_score)
        delta = k * g * (w_home - we_home)

        self.ratings[home] = r_home + delta
        self.ratings[away] = r_away - delta   # אפס-סכום
        return delta, -delta

    def run(self, matches) -> dict[str, float]:
        """
        מריץ Elo כרונולוגית על רצף משחקים.
        כל פריט: אובייקט עם השדות date, home_team, away_team,
        home_score, away_score, tournament, neutral.
        מחזיר את מילון הדירוגים הסופי (כל הנבחרות בהיסטוריה).
        """
        for m in sorted(matches, key=lambda x: x.date):
            self.update_match(
                m.home_team, m.away_team,
                m.home_score, m.away_score,
                m.tournament, bool(m.neutral),
            )
        return self.ratings
