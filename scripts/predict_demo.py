"""
הדגמת תחזית (שלב 3) — מפיק תחזיות למשחקי מונדיאל 2026 אמיתיים.
הרצה:  python -m scripts.predict_demo
"""
from __future__ import annotations

from prediction import engine

DEMOS = [
    ("Spain", "South Korea"),
    ("Brazil", "Scotland"),
    ("Argentina", "Jordan"),
    ("Germany", "Ivory Coast"),
    ("England", "Croatia"),
    ("USA", "Paraguay"),
]


def bar(p: float, width: int = 20) -> str:
    return "█" * round(p * width)


def main() -> None:
    print("בונה מודל מהנתונים ההיסטוריים...")
    model = engine.build_model()
    print(f"μ (בסיס שערים)={model.s.mu:.2f} | יתרון בית={model.s.home_factor:.3f}\n")

    for home, away in DEMOS:
        p = model.predict(home, away, neutral=True)
        print("=" * 52)
        print(f"  {home}  נגד  {away}   (מגרש ניטרלי)")
        print("-" * 52)
        print(f"  ניצחון {home:14} {p.p_home*100:5.1f}%  {bar(p.p_home)}")
        print(f"  תיקו           {'':9} {p.p_draw*100:5.1f}%  {bar(p.p_draw)}")
        print(f"  ניצחון {away:14} {p.p_away*100:5.1f}%  {bar(p.p_away)}")
        print(f"  תוחלת שערים: {p.exp_home_goals:.2f} - {p.exp_away_goals:.2f}")
        print(f"  תוצאה סבירה: {p.likely_score}   | ביטחון: {p.confidence}")
        tops = "  ".join(f"{t['score']} ({t['prob']*100:.0f}%)" for t in p.top_scores)
        print(f"  5 מובילות: {tops}")
    print("=" * 52)


if __name__ == "__main__":
    main()
