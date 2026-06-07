"""
חוזקי התקפה/הגנה משוקללים (לכל נבחרת).

לכל משחק היסטורי משקל  w = עדכניות × חשיבות.
מתוך אלה נאמדים, "נכון לתאריך ייחוס":
  • μ   — ממוצע שערים משוקלל לקבוצה למשחק (בסיס הליגה)
  • attack_i  = קצב הכבישה המשוקלל של i  / μ
  • defense_i = קצב הספיגה המשוקלל של i  / μ
שתי הנבחרות עם מעט נתונים מכווצות (shrinkage) לכיוון הממוצע (1.0)
כדי למנוע הערכות-יתר — בדיוק כמו שתואר באפיון.

ניתן לאמוד "נכון לתאריך" כדי שה-Backtest ישתמש רק במידע שקדם למשחק.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

import config
from ratings.weights import importance_weight, recency_weight


def _parse(d: str) -> date:
    y, m, day = d.split("-")
    return date(int(y), int(m), int(day))


@dataclass
class StrengthModel:
    mu: float = 1.35                       # בסיס שערים לקבוצה למשחק
    attack: dict[str, float] = None        # מכפיל התקפה לכל נבחרת
    defense: dict[str, float] = None       # מכפיל הגנה לכל נבחרת
    home_factor: float = 1.0               # יתרון מארחת (מגרש לא-ניטרלי)
    shrink_weight: float = 5.0             # "משקל-דמה" לכיווץ לעבר הממוצע

    def attack_of(self, team: str) -> float:
        return (self.attack or {}).get(team, 1.0)

    def defense_of(self, team: str) -> float:
        return (self.defense or {}).get(team, 1.0)

    def fit(self, matches, ref_date: date, half_life_days: float = None) -> "StrengthModel":
        """
        matches: פריטים עם date, home_team, away_team, home_score,
                 away_score, tournament, neutral.
        ref_date: רק משחקים שקדמו לתאריך זה נספרים.
        """
        half_life = half_life_days or config.RECENCY_HALF_LIFE_DAYS

        scored_w = defaultdict(float)   # Σ w·שערים שכבשה
        conceded_w = defaultdict(float)  # Σ w·שערים שספגה
        weight_sum = defaultdict(float)  # Σ w (מספר משחקים אפקטיבי)

        tot_goals_w = 0.0
        tot_w = 0.0
        # יתרון בית: שערי בית מול שערי חוץ במשחקים לא-ניטרליים
        home_goals_w = away_goals_w = nonneutral_w = 0.0

        for m in matches:
            md = _parse(m.date)
            if md >= ref_date:
                continue
            w = recency_weight(md, ref_date, half_life) * importance_weight(m.tournament)
            if w <= 1e-9:
                continue
            h, a = m.home_team, m.away_team
            hs, as_ = m.home_score, m.away_score

            scored_w[h] += w * hs
            conceded_w[h] += w * as_
            weight_sum[h] += w
            scored_w[a] += w * as_
            conceded_w[a] += w * hs
            weight_sum[a] += w

            tot_goals_w += w * (hs + as_)
            tot_w += w
            if not m.neutral:
                home_goals_w += w * hs
                away_goals_w += w * as_
                nonneutral_w += w

        # בסיס: ממוצע שערים לקבוצה למשחק
        self.mu = (tot_goals_w / tot_w / 2.0) if tot_w > 0 else 1.35

        # יתרון מארחת (יחס שערי בית לשערי חוץ, מנורמל)
        if nonneutral_w > 0 and away_goals_w > 0:
            ratio = (home_goals_w / nonneutral_w) / (away_goals_w / nonneutral_w)
            self.home_factor = ratio ** 0.5   # מתון
        else:
            self.home_factor = 1.0

        # מכפילי התקפה/הגנה עם כיווץ לעבר 1.0
        self.attack, self.defense = {}, {}
        s = self.shrink_weight
        for team, wsum in weight_sum.items():
            atk_rate = scored_w[team] / wsum
            def_rate = conceded_w[team] / wsum
            # כיווץ: ככל שיש פחות נתונים (wsum קטן), מתקרבים ל-μ
            atk_shrunk = (scored_w[team] + s * self.mu) / (wsum + s)
            def_shrunk = (conceded_w[team] + s * self.mu) / (wsum + s)
            self.attack[team] = atk_shrunk / self.mu
            self.defense[team] = def_shrunk / self.mu
        return self
