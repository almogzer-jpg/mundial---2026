"""
מודל Dixon-Coles (Poisson דו-משתני) — לב התחזיות.

תוחלת השערים נגזרת משילוב שני אותות:
  • עליונות התקפה/הגנה (מהמודל המשוקלל) — משקל β
  • עליונות מבוססת Elo                  — משקל (1−β)   ← הריסון לעבר Elo
סך השערים נלקח ממודל ההתקפה/הגנה. מטריצת התוצאות נבנית מ-Poisson
עם תיקון Dixon-Coles לתוצאות נמוכות.

פלט לכל משחק: P(נצ'/תיקו/הפ'), 5 תוצאות מובילות, תוצאה סבירה,
תוחלת שערים, ורמת ביטחון.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import poisson

import config
from prediction.strength import StrengthModel


@dataclass
class Prediction:
    home: str
    away: str
    p_home: float
    p_draw: float
    p_away: float
    exp_home_goals: float
    exp_away_goals: float
    likely_score: str
    top_scores: list[dict]      # [{"score": "2-1", "prob": 0.09}, ...]
    confidence: str             # low / medium / high
    p_home_big: float = 0.0     # סיכוי ניצחון בית בהפרש 3+
    p_away_big: float = 0.0     # סיכוי ניצחון חוץ בהפרש 3+


class PoissonModel:
    def __init__(
        self,
        strength: StrengthModel,
        elo: dict[str, float],
        rho: float = config.DC_RHO,
        beta: float = config.ELO_BLEND_BETA,
        elo_to_goals: float = config.ELO_TO_GOALS,
        max_goals: int = config.MAX_GOALS,
        elo_home_adv: float = config.ELO_HOME_ADVANTAGE,
        availability: dict[str, float] | None = None,
    ):
        self.s = strength
        self.elo = elo
        self.rho = rho
        self.beta = beta
        self.elo_to_goals = elo_to_goals
        self.max_goals = max_goals
        self.elo_home_adv = elo_home_adv
        self.availability = availability or {}

    def _elo(self, team: str) -> float:
        return self.elo.get(team, config.ELO_INITIAL)

    def _avail(self, team: str) -> float:
        return self.availability.get(team, 1.0)

    def expected_goals(self, home: str, away: str, neutral: bool,
                       home_delta: float = 0.0, away_delta: float = 0.0) -> tuple[float, float]:
        hf = 1.0 if neutral else self.s.home_factor
        av_h, av_a = self._avail(home), self._avail(away)
        # אות התקפה/הגנה (קבוצה פצועה כובשת פחות)
        lam_h_ad = self.s.mu * self.s.attack_of(home) * av_h * self.s.defense_of(away) * hf
        lam_a_ad = self.s.mu * self.s.attack_of(away) * av_a * self.s.defense_of(home) / hf
        sup_ad = lam_h_ad - lam_a_ad
        total = lam_h_ad + lam_a_ad

        # אות Elo (פציעות + התאמות פר-משחק מסעיפים 1-8)
        elo_adv = 0.0 if neutral else self.elo_home_adv
        eff_elo_h = self._elo(home) - (1.0 - av_h) * config.INJURY_ELO_SCALE + home_delta
        eff_elo_a = self._elo(away) - (1.0 - av_a) * config.INJURY_ELO_SCALE + away_delta
        sup_elo = self.elo_to_goals * (eff_elo_h - eff_elo_a + elo_adv)

        # שילוב העליונות; הסך נשמר ממודל ההתקפה/הגנה
        sup = self.beta * sup_ad + (1.0 - self.beta) * sup_elo
        lam_h = max(0.05, (total + sup) / 2.0)
        lam_a = max(0.05, (total - sup) / 2.0)
        return lam_h, lam_a

    def score_matrix(self, lam_h: float, lam_a: float) -> np.ndarray:
        n = self.max_goals + 1
        ph = poisson.pmf(np.arange(n), lam_h)
        pa = poisson.pmf(np.arange(n), lam_a)
        m = np.outer(ph, pa)
        # תיקון Dixon-Coles לארבע התוצאות הנמוכות
        r = self.rho
        m[0, 0] *= 1 - lam_h * lam_a * r
        m[0, 1] *= 1 + lam_h * r
        m[1, 0] *= 1 + lam_a * r
        m[1, 1] *= 1 - r
        return m / m.sum()

    def predict(self, home: str, away: str, neutral: bool = True,
                home_delta: float = 0.0, away_delta: float = 0.0) -> Prediction:
        lam_h, lam_a = self.expected_goals(home, away, neutral, home_delta, away_delta)
        m = self.score_matrix(lam_h, lam_a)

        p_home = float(np.tril(m, -1).sum())   # שורה>עמודה => בית כובש יותר
        p_away = float(np.triu(m, 1).sum())
        p_draw = float(np.trace(m))

        # 5 התוצאות הסבירות
        flat = [
            (i, j, float(m[i, j]))
            for i in range(m.shape[0])
            for j in range(m.shape[1])
        ]
        flat.sort(key=lambda x: x[2], reverse=True)
        top = [{"score": f"{i}-{j}", "prob": round(p, 4)} for i, j, p in flat[:5]]
        likely = top[0]["score"]

        return Prediction(
            home=home, away=away,
            p_home=round(p_home, 4),
            p_draw=round(p_draw, 4),
            p_away=round(p_away, 4),
            exp_home_goals=round(lam_h, 2),
            exp_away_goals=round(lam_a, 2),
            likely_score=likely,
            top_scores=top,
            confidence=self._confidence(p_home, p_draw, p_away),
            p_home_big=round(float(np.tril(m, -3).sum()), 4),   # בית מנצח ב-3+
            p_away_big=round(float(np.triu(m, 3).sum()), 4),    # חוץ מנצח ב-3+
        )

    @staticmethod
    def _confidence(p_home: float, p_draw: float, p_away: float) -> str:
        top = max(p_home, p_draw, p_away)
        if top >= config.CONFIDENCE_HIGH:
            return "high"
        if top >= config.CONFIDENCE_MEDIUM:
            return "medium"
        return "low"
