"""
מחקר אופטימיזציה — מכייל את פרמטרי המודל על מונדיאלים 2010-2022.

יעיל: Elo נבנה פעם אחת לכל מונדיאל (לא תלוי ב-half_life/shrink),
החוזקים נבנים מחדש לכל (half_life, shrink), והפרמטרים הזולים
(beta, elo_to_goals, rho, temperature) נסרקים בלולאה פנימית.

מודד Log-loss מצרפי + פירוק לכל מונדיאל (לוודא שלא overfit לאחד).
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import poisson

import config
from data import db
from prediction import backtest
from prediction.strength import StrengthModel
from ratings.elo import EloEngine

# --- גרידים לסריקה ---
HALF_LIVES = [270, 365, 500, 730]
SHRINKS = [3.0, 5.0, 8.0]
BETAS = [0.3, 0.4, 0.5, 0.6]
E2GS = [0.004, 0.005, 0.006, 0.007]
RHOS = [-0.05, 0.0, 0.05]
TEMPS = [0.85, 0.95, 1.0, 1.1, 1.25]
MAXG = config.MAX_GOALS


def wdl(lam_h, lam_a, rho):
    """מחזיר (p_home, p_draw, p_away) ממטריצת Dixon-Coles."""
    n = MAXG + 1
    ph = poisson.pmf(np.arange(n), lam_h)
    pa = poisson.pmf(np.arange(n), lam_a)
    m = np.outer(ph, pa)
    m[0, 0] *= 1 - lam_h * lam_a * rho
    m[0, 1] *= 1 + lam_h * rho
    m[1, 0] *= 1 + lam_a * rho
    m[1, 1] *= 1 - rho
    m /= m.sum()
    return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())


def main():
    print("טוען נתונים ובונה Elo לכל מונדיאל (פעם אחת)...")
    with db.connection() as conn:
        all_matches = backtest.load_all(conn)

    # Elo + רשימת משחקים לכל מונדיאל (Elo לא תלוי ב-half_life/shrink)
    editions = []
    for y in backtest.WC_YEARS:
        wc = [m for m in all_matches
              if m.tournament == "FIFA World Cup" and m.date.startswith(str(y))]
        if not wc:
            continue
        start = backtest._parse(min(m.date for m in wc))
        prior = [m for m in all_matches if backtest._parse(m.date) < start]
        elo = EloEngine().run(prior)
        editions.append((y, elo, prior, start, wc))

    def precompute(strengths_by_year):
        """לכל משחק: (total_ad, sup_ad, elo_diff, outcome, year)."""
        rows = []
        for y, elo, prior, start, wc in editions:
            s = strengths_by_year[y]
            for mt in wc:
                h, a = mt.home_team, mt.away_team
                hf = 1.0 if mt.neutral else s.home_factor
                lh = s.mu * s.attack_of(h) * s.defense_of(a) * hf
                la = s.mu * s.attack_of(a) * s.defense_of(h) / hf
                elo_adv = 0.0 if mt.neutral else config.ELO_HOME_ADVANTAGE
                ediff = elo.get(h, 1500) - elo.get(a, 1500) + elo_adv
                oc = 0 if mt.home_score > mt.away_score else (2 if mt.home_score < mt.away_score else 1)
                rows.append((lh + la, lh - la, ediff, oc, y))
        return rows

    def score(rows, beta, e2g, rho, temp):
        per_year = {}
        ll = n = correct = 0.0
        for total, sup_ad, ediff, oc, y in rows:
            sup = beta * sup_ad + (1 - beta) * e2g * ediff
            lh = max(0.05, (total + sup) / 2)
            la = max(0.05, (total - sup) / 2)
            ph, pd, pa = wdl(lh, la, rho)
            probs = np.array([ph, pd, pa]) ** (1.0 / temp)
            probs /= probs.sum()
            ll -= math.log(max(probs[oc], 1e-9))
            correct += int(np.argmax(probs) == oc)
            n += 1
            d = per_year.setdefault(y, [0.0, 0])
            d[0] -= math.log(max(probs[oc], 1e-9)); d[1] += 1
        return ll / n, correct / n, {y: d[0] / d[1] for y, d in per_year.items()}

    best = None
    for hl in HALF_LIVES:
        for sh in SHRINKS:
            strengths = {y: StrengthModel(shrink_weight=sh).fit(prior, start, hl)
                         for y, elo, prior, start, wc in editions}
            rows = precompute(strengths)
            for beta in BETAS:
                for e2g in E2GS:
                    for rho in RHOS:
                        for temp in TEMPS:
                            ll, acc, per_year = score(rows, beta, e2g, rho, temp)
                            if best is None or ll < best["ll"]:
                                best = {"ll": ll, "acc": acc, "hl": hl, "sh": sh,
                                        "beta": beta, "e2g": e2g, "rho": rho,
                                        "temp": temp, "per_year": per_year}
        print(f"  ...סיים half_life={hl}, הטוב עד כה: Log-loss={best['ll']:.4f}")

    print("\n" + "=" * 56)
    print("הפרמטרים המיטביים שנמצאו:")
    print(f"  half_life={best['hl']}  shrink={best['sh']}  beta={best['beta']}")
    print(f"  elo_to_goals={best['e2g']}  rho={best['rho']}  temperature={best['temp']}")
    print(f"\n  Log-loss={best['ll']:.4f}  (בסיס: 0.9913)")
    print(f"  דיוק={best['acc']*100:.1f}%")
    print("  פירוק לפי מונדיאל (Log-loss):")
    for y, v in sorted(best["per_year"].items()):
        print(f"     {y}: {v:.4f}")


if __name__ == "__main__":
    main()
