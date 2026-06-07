"""
Backtest וכיול — בודק את המודל על מונדיאלים 2010-2022.

לכל מונדיאל: מחשב Elo + חוזקים *נכון לתחילת הטורניר* (out-of-sample),
חוזה כל משחק, ומשווה לתוצאה בפועל. מודד:
  • Log-loss  ו-Brier  (איכות ההסתברויות — נמוך = טוב)
  • דיוק (% שבו הזוכה החזוי תאם)
  • פגיעה בתוצאה המדויקת

הפרמטרים β, elo_to_goals, ρ אינם משפיעים על Elo/חוזקים — לכן מחשבים
אותם פעם אחת לכל מונדיאל ומעריכים שילובי פרמטרים רבים בזול (grid search).
"""
from __future__ import annotations

import math
from collections import namedtuple
from datetime import date

import config
from data import db
from prediction.poisson import PoissonModel
from prediction.strength import StrengthModel
from ratings.elo import EloEngine

Match = namedtuple(
    "Match",
    "date home_team away_team home_score away_score tournament neutral",
)
WC_YEARS = [2010, 2014, 2018, 2022]


def _parse(d: str) -> date:
    y, m, day = d.split("-")
    return date(int(y), int(m), int(day))


def load_all(conn) -> list[Match]:
    rows = conn.execute(
        "SELECT date, home_team, away_team, home_score, away_score, "
        "tournament, neutral FROM historical_matches ORDER BY date"
    ).fetchall()
    return [Match(*r) for r in rows]


def edition_context(all_matches, year):
    """מחזיר (elo, strength, wc_matches) נכון לתחילת המונדיאל של אותה שנה."""
    wc = [
        m for m in all_matches
        if m.tournament == "FIFA World Cup" and m.date.startswith(str(year))
    ]
    if not wc:
        return None
    start = _parse(min(m.date for m in wc))
    prior = [m for m in all_matches if _parse(m.date) < start]

    elo = EloEngine().run(prior)
    strength = StrengthModel().fit(prior, start)
    return elo, strength, wc


def evaluate(contexts, beta, elo_to_goals, rho):
    """מעריך שילוב פרמטרים על כל המונדיאלים. מחזיר מדדים מצרפיים."""
    ll = brier = 0.0
    n = correct = exact = 0
    for elo, strength, wc in contexts:
        model = PoissonModel(
            strength, elo, rho=rho, beta=beta, elo_to_goals=elo_to_goals
        )
        for m in wc:
            pred = model.predict(m.home_team, m.away_team, neutral=bool(m.neutral))
            # תוצאה בפועל
            if m.home_score > m.away_score:
                outcome, probs = 0, (pred.p_home, pred.p_draw, pred.p_away)
            elif m.home_score < m.away_score:
                outcome, probs = 2, (pred.p_home, pred.p_draw, pred.p_away)
            else:
                outcome, probs = 1, (pred.p_home, pred.p_draw, pred.p_away)

            p_actual = max(probs[outcome], 1e-6)
            ll -= math.log(p_actual)
            brier += sum(
                (p - (1.0 if i == outcome else 0.0)) ** 2 for i, p in enumerate(probs)
            )
            if max(range(3), key=lambda i: probs[i]) == outcome:
                correct += 1
            if pred.likely_score == f"{m.home_score}-{m.away_score}":
                exact += 1
            n += 1
    return {
        "n": n,
        "log_loss": ll / n,
        "brier": brier / n,
        "accuracy": correct / n,
        "exact_hit": exact / n,
    }


def main() -> None:
    print("=" * 56)
    print("Backtest וכיול — מונדיאלים 2010-2022")
    print("=" * 56)
    with db.connection() as conn:
        all_matches = load_all(conn)

    contexts = [c for y in WC_YEARS if (c := edition_context(all_matches, y))]
    total_games = sum(len(wc) for _, _, wc in contexts)
    print(f"נטענו {len(contexts)} מונדיאלים, {total_games} משחקים לבדיקה.\n")

    # baseline בפרמטרים הנוכחיים
    base = evaluate(contexts, config.ELO_BLEND_BETA, config.ELO_TO_GOALS, config.DC_RHO)
    print(f"פרמטרי פתיחה (β={config.ELO_BLEND_BETA}, "
          f"elo2g={config.ELO_TO_GOALS}, ρ={config.DC_RHO}):")
    print(f"  Log-loss={base['log_loss']:.4f}  Brier={base['brier']:.4f}  "
          f"דיוק={base['accuracy']*100:.1f}%  תוצאה מדויקת={base['exact_hit']*100:.1f}%\n")

    # grid search לכיול
    print("מכייל (grid search)...")
    best = None
    for beta in (0.3, 0.4, 0.5, 0.6, 0.7):
        for e2g in (0.002, 0.003, 0.004, 0.005):
            for rho in (-0.10, -0.05, 0.0):
                r = evaluate(contexts, beta, e2g, rho)
                if best is None or r["log_loss"] < best["log_loss"]:
                    best = {**r, "beta": beta, "elo_to_goals": e2g, "rho": rho}

    print("\n--- הפרמטרים המיטביים (מינימום Log-loss) ---")
    print(f"  β={best['beta']}  elo_to_goals={best['elo_to_goals']}  ρ={best['rho']}")
    print(f"  Log-loss={best['log_loss']:.4f}  Brier={best['brier']:.4f}  "
          f"דיוק={best['accuracy']*100:.1f}%  תוצאה מדויקת={best['exact_hit']*100:.1f}%")

    # השוואה: ניחוש אקראי = log-loss ln(3)=1.0986
    print(f"\n  (לעיון: ניחוש אחיד = Log-loss {math.log(3):.4f}, דיוק 33%)")


if __name__ == "__main__":
    main()
