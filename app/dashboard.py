"""
דשבורד מונדיאל 2026 — Streamlit.
הרצה:  streamlit run app/dashboard.py
"""
from __future__ import annotations

import json
import os
import sys

import streamlit as st

# ודא ששורש הפרויקט ב-PATH (חשוב בענן: streamlit run app/dashboard.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import update
from app import flags, services
from ingestion.providers.manual import OVERRIDES_PATH

st.set_page_config(page_title="חיזוי מונדיאל 2026", page_icon="⚽", layout="wide")

# עיצוב קל + יישור ימני לעברית
st.markdown(
    "<style>.stApp{direction:rtl;} .stDataFrame{direction:ltr;} "
    "h1,h2,h3,p,label,div{text-align:right;}</style>",
    unsafe_allow_html=True,
)

CONF_HE = {"high": "גבוהה 🟢", "medium": "בינונית 🟡", "low": "נמוכה 🔴"}


@st.cache_resource(show_spinner="בונה את מסד הנתונים בפעם הראשונה (מוריד נתונים פתוחים)...")
def ensure_initialized():
    """בהרצה ראשונה (למשל בענן) — בונה את ה-DB מאפס אם הוא ריק."""
    from data import db
    db.init_db()
    with db.connection() as conn:
        n_teams = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    if n_teams == 0:
        update.full_refresh()
    return True


@st.cache_resource
def get_model():
    return services.build_model()


@st.cache_data(show_spinner=False)
def get_sim(n_runs: int, played: int):
    # played בחתימה כדי לרענן כשמוזנות תוצאות
    return services.simulate_tournament(get_model(), n_runs=n_runs)


def wdl_bar(p_home, p_draw, p_away, home, away):
    h, d, a = p_home * 100, p_draw * 100, p_away * 100
    st.markdown(
        f"<div style='display:flex;height:34px;border-radius:6px;overflow:hidden;"
        f"font-size:13px;color:#fff;text-align:center;line-height:34px'>"
        f"<div style='width:{h}%;background:#2e7d32'>{h:.0f}%</div>"
        f"<div style='width:{d}%;background:#9e9e9e'>{d:.0f}%</div>"
        f"<div style='width:{a}%;background:#1565c0'>{a:.0f}%</div></div>"
        f"<div style='display:flex;justify-content:space-between;font-size:13px'>"
        f"<b>{home}</b><span>תיקו</span><b>{away}</b></div>",
        unsafe_allow_html=True,
    )


# ============ מסכים ============
def screen_dashboard():
    st.title("⚽ חיזוי מונדיאל 2026")
    model = get_model()
    fixtures = services.load_fixtures()
    upcoming = [f for f in fixtures if f["status"] == "NS"][:6]
    played = sum(1 for f in fixtures if f["home_goals"] is not None)

    c1, c2, c3 = st.columns(3)
    c1.metric("נבחרות", len(services.load_teams()))
    c2.metric("משחקי בתים", len([f for f in fixtures if f["grp"]]))
    c3.metric("שוחקו", played)

    st.subheader("🔮 תחזיות למשחקים הקרובים")
    for f in upcoming:
        p = services.predict(model, f["home"], f["away"], neutral=bool(f["is_neutral"]))
        with st.container(border=True):
            st.caption(f"{services.fmt_date(f['date_utc'])} · בית {f['grp']} · {f['city'] or ''}")
            wdl_bar(p.p_home, p.p_draw, p.p_away,
                    flags.name_html(f["home"]), flags.name_html(f["away"]))
            st.write(f"תוצאה סבירה: **{p.likely_score}** · ביטחון: {CONF_HE[p.confidence]}")

    st.subheader("🏆 מועמדות לזכייה")
    probs, played_n, _ = get_sim(config.MONTE_CARLO_RUNS, played)
    ranked = sorted(probs.items(), key=lambda kv: kv[1]["winner"], reverse=True)[:8]
    st.dataframe(
        [{"דגל": flags.flag_url(t), "נבחרת": t, "אלופה %": round(p["winner"] * 100, 1),
          "גמר %": round(p["final"] * 100, 1), "עולה %": round(p["advance"] * 100, 1)}
         for t, p in ranked],
        use_container_width=True, hide_index=True,
        column_config={"דגל": st.column_config.ImageColumn("")},
    )


def screen_match():
    st.title("⚽ תחזית משחק")
    model = get_model()
    teams = [t["name"] for t in services.load_teams()]
    c1, c2, c3 = st.columns([2, 2, 1])
    home = c1.selectbox("נבחרת א'", teams, index=0)
    away = c2.selectbox("נבחרת ב'", teams, index=1)
    neutral = c3.checkbox("מגרש ניטרלי", value=True)
    if home == away:
        st.warning("בחר שתי נבחרות שונות.")
        return

    p = services.predict(model, home, away, neutral)
    st.markdown(f"### {flags.name_html(home)} נגד {flags.name_html(away)}",
                unsafe_allow_html=True)
    wdl_bar(p.p_home, p.p_draw, p.p_away,
            flags.name_html(home), flags.name_html(away))
    c1, c2, c3 = st.columns(3)
    c1.metric("תוצאה סבירה", p.likely_score)
    c2.metric("תוחלת שערים", f"{p.exp_home_goals:.2f} - {p.exp_away_goals:.2f}")
    c3.metric("רמת ביטחון", CONF_HE[p.confidence])

    # מחוון אמינות הנתונים
    if services.confidence_level(home, away) == "strong":
        st.success("🟢 תחזית מבוססת נתונים חזקים (Elo היסטורי + סגל נוכחי)")
    else:
        st.warning("🟡 תחזית חלקית — חסרים נתוני סגל מלאים לאחת הנבחרות")

    # מה השפיע על התחזית
    with st.expander("🔍 מה השפיע על התחזית"):
        for side in (home, away):
            ti = services.team_info(side)
            base = ti.get("elo") or config.ELO_INITIAL
            adj = config.CTS_WEIGHT * (ti.get("squad_adj") or 0.0)
            avail = model.availability.get(side, 1.0)
            st.markdown(
                f"**{flags.name_html(side)}** — Elo היסטורי **{base:.0f}** · "
                f"כוח-סגל נוכחי **{adj:+.0f}** · זמינות **{avail*100:.0f}%**",
                unsafe_allow_html=True)
        st.caption("Final Rating = Elo היסטורי + כוח-סגל נוכחי + מוטיבציה. "
                   "טופס עדכני וסוג המשחק משוקללים בתוך המודל.")

    # פוטנציאל ניצחון גדול
    big, who = (p.p_home_big, home) if p.p_home_big >= p.p_away_big else (p.p_away_big, away)
    if big >= 0.10:
        st.info(f"💥 סיכוי ש**{who}** תנצח בהפרש **3+ שערים**: {big*100:.0f}%")

    st.subheader("5 התוצאות הסבירות ביותר")
    st.dataframe(
        [{"תוצאה": t["score"], "הסתברות %": round(t["prob"] * 100, 1)} for t in p.top_scores],
        use_container_width=True, hide_index=True,
    )

    # פציעות (אם יש) + השפעתן על הזמינות
    injuries = services.injuries_by_team()
    for side in (home, away):
        if injuries.get(side):
            avail = model.availability.get(side, 1.0)
            st.warning(f"🚑 {side} — חסרים: {', '.join(injuries[side])} "
                       f"(זמינות {avail*100:.0f}%)")


def screen_groups():
    st.title("📊 טבלאות הבתים")
    tables = services.standings()
    cols = st.columns(2)
    for i, (g, rows) in enumerate(sorted(tables.items())):
        with cols[i % 2]:
            st.subheader(f"בית {g}")
            st.dataframe(
                [{"#": r + 1, "דגל": flags.flag_url(row.team), "נבחרת": row.team,
                  "מש'": row.played, "נצ'": row.win, "תיקו": row.draw,
                  "הפ'": row.loss, "+/-": row.gd, "נק'": row.points}
                 for r, row in enumerate(rows)],
                use_container_width=True, hide_index=True,
                column_config={"דגל": st.column_config.ImageColumn("")},
            )


BRACKET_CSS = """
<style>
.bracket{display:flex;direction:ltr;overflow-x:auto;gap:4px;padding:10px 0;
  font-size:12px;align-items:stretch}
.round{display:flex;flex-direction:column;justify-content:space-around;
  min-width:148px;flex:0 0 auto}
.rname{font-weight:700;text-align:center;color:#1565c0;margin-bottom:6px;
  position:sticky;top:0}
.match{background:#fff;border:1px solid #d0d7de;border-radius:6px;margin:4px 3px;
  padding:3px 6px;box-shadow:0 1px 2px rgba(0,0,0,.06)}
.team{display:flex;align-items:center;gap:5px;padding:2px 0;white-space:nowrap}
.team.win{font-weight:700;color:#1b7f34}
.team.lose{color:#9aa0a6}
.team img{height:13px;border-radius:2px}
.pp{margin-inline-start:auto;font-size:10px;color:#888}
.org{font-size:9px;color:#9aa0a6;margin-inline-start:18px;margin-top:-3px;margin-bottom:2px}
.champ{display:flex;align-items:center;gap:6px;justify-content:center;
  background:#fff8e1;border:2px solid #f4c430;border-radius:8px;padding:10px;font-size:14px}
</style>
"""


def _team_row(name, is_win, prob=None, origin=None):
    cls = "win" if is_win else "lose"
    pp = f"<span class='pp'>{prob}%</span>" if (is_win and prob is not None) else ""
    org = f"<div class='org'>{origin}</div>" if origin else ""
    return (f"<div class='team {cls}'>{flags.img(name)}<span>{name}</span>{pp}</div>{org}")


def bracket_html(rounds, champion):
    cols = ""
    for rnd in rounds:
        mh = ""
        for m in rnd["matches"]:
            hw = m["winner"] == m["home"]
            mh += ("<div class='match'>"
                   + _team_row(m["home"], hw, m["prob"] if hw else None, m.get("home_from"))
                   + _team_row(m["away"], not hw, m["prob"] if not hw else None, m.get("away_from"))
                   + "</div>")
        cols += f"<div class='round'><div class='rname'>{rnd['name']}</div>{mh}</div>"
    champ = ""
    if champion:
        champ = (f"<div class='round'><div class='rname'>🏆 אלוף</div>"
                 f"<div class='champ'>{flags.img(champion, 22)}<b>{champion}</b></div></div>")
    return BRACKET_CSS + f"<div class='bracket'>{cols}{champ}</div>"


def screen_knockout():
    st.title("🏆 שלב הנוקאאוט")
    fixtures = services.load_fixtures()
    played = sum(1 for f in fixtures if f["home_goals"] is not None)
    total_groups = len([f for f in fixtures if f["grp"]])

    # עץ הנוקאאוט החזוי (ויזואלי)
    st.subheader("🌳 עץ הנוקאאוט החזוי")
    if played < total_groups:
        st.info("שלב הבתים טרם הסתיים — זהו המסלול הסביר ביותר לפי המודל. "
                "מתעדכן עם הזנת תוצאות.")
    model = get_model()
    rounds, champion = services.projected_bracket(model)
    st.markdown(bracket_html(rounds, champion), unsafe_allow_html=True)
    st.caption("מודגש בירוק = המנצח החזוי בכל שלב, עם הסתברות הניצחון.")

    st.divider()
    st.subheader("📊 סיכויי התקדמות (כל הנבחרות)")
    probs, _, _ = get_sim(config.MONTE_CARLO_RUNS, played)
    st.caption(f"מבוסס {config.MONTE_CARLO_RUNS:,} סימולציות.")
    ranked = sorted(probs.items(), key=lambda kv: kv[1]["winner"], reverse=True)
    st.dataframe(
        [{"דגל": flags.flag_url(t), "נבחרת": t, "עולה %": round(p["advance"] * 100, 1),
          "1/8 %": round(p["round16"] * 100, 1), "1/4 %": round(p["quarter"] * 100, 1),
          "1/2 %": round(p["semi"] * 100, 1), "גמר %": round(p["final"] * 100, 1),
          "אלופה %": round(p["winner"] * 100, 1)} for t, p in ranked],
        use_container_width=True, hide_index=True,
        column_config={"דגל": st.column_config.ImageColumn("")},
    )


def screen_scorers():
    st.title("👟 תחזית מלך שערים")
    fixtures = services.load_fixtures()
    played = sum(1 for f in fixtures if f["home_goals"] is not None)
    probs, _, _ = get_sim(config.MONTE_CARLO_RUNS, played)
    ranked = services.golden_boot(probs)

    st.caption("הערכה: שערי הקבוצה הצפויים בטורניר × נתח החלוץ המוביל. "
               "מתעדכן עם התוצאות.")
    if ranked:
        top = ranked[0]
        st.success(f"🏅 המועמד המוביל: **{top['player']}** ({top['team']}) — "
                   f"כ-{top['exp_goals']:.1f} שערים צפויים")
    st.dataframe(
        [{"#": i + 1, "דגל": flags.flag_url(r["team"]), "שחקן": r["player"],
          "נבחרת": r["team"], "שערים צפויים": r["exp_goals"]}
         for i, r in enumerate(ranked[:15])],
        use_container_width=True, hide_index=True,
        column_config={"דגל": st.column_config.ImageColumn("")},
    )


def screen_team():
    st.title("👤 פרופיל נבחרת")
    teams = [t["name"] for t in services.load_teams()]
    team = st.selectbox("בחר נבחרת", teams)
    info = next(t for t in services.load_teams() if t["name"] == team)
    st.markdown(f"### {flags.name_html(team, height=20)}", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("דירוג Elo", f"{info['elo']:.0f}")
    c2.metric("בית", info["grp"])
    adj = config.CTS_WEIGHT * (info.get("squad_adj") or 0.0)
    c3.metric("כוח סגל (התאמה)", f"{adj:+.0f}")
    eff = (info["elo"] or config.ELO_INITIAL) + adj
    c4.metric("Rating אפקטיבי", f"{eff:.0f}")

    players = services.squad(team)
    if players:
        st.subheader(f"הסגל הנוכחי ({len(players)} שחקנים)")
        st.dataframe(
            [{"שחקן": pl["name"], "עמדה": pl["pos"], "גיל": pl["age"],
              "קאפים": pl["caps"], "שערים": pl["goals"], "מועדון": pl["club"]}
             for pl in players],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("אין נתוני סגל לנבחרת זו (התחזית מבוססת על Elo בלבד).")

    hist = services.elo_history(team)
    if hist:
        st.subheader("היסטוריית Elo")
        import pandas as pd
        df = pd.DataFrame(hist).tail(150)
        df["date"] = pd.to_datetime(df["date"])
        st.line_chart(df.set_index("date")["rating"])


def screen_manual():
    st.title("✍️ הזנת תוצאה ידנית")
    st.caption("הזנת תוצאה מעדכנת את הטבלאות, הדירוגים והתחזיות.")
    fixtures = services.load_fixtures()
    options = {f"{services.fmt_date(f['date_utc'])} · {f['home']} - {f['away']}": f
               for f in fixtures if f["grp"]}
    label = st.selectbox("בחר משחק", list(options.keys()))
    f = options[label]
    st.markdown(f"{flags.name_html(f['home'], 18)} נגד {flags.name_html(f['away'], 18)}",
                unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    hs = c1.number_input(f"שערי {f['home']}", 0, 20, 0)
    as_ = c2.number_input(f"שערי {f['away']}", 0, 20, 0)

    if st.button("💾 שמור ועדכן"):
        data = {}
        if OVERRIDES_PATH.exists():
            data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
        data.setdefault("results", [])
        data["results"] = [r for r in data["results"]
                           if not (r["home"] == f["home"] and r["away"] == f["away"])]
        data["results"].append({
            "date": f["date_utc"], "home": f["home"], "away": f["away"],
            "group": f["grp"], "home_score": int(hs), "away_score": int(as_),
            "neutral": bool(f["is_neutral"]),
        })
        OVERRIDES_PATH.parent.mkdir(exist_ok=True)
        OVERRIDES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        with st.spinner("מעדכן דירוגים, טבלאות ותחזיות..."):
            summary = update.full_refresh()
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success(f"נשמר: {f['home']} {hs}-{as_} {f['away']}. "
                   f"עודכנו {summary['ratings']} דירוגים ו-{summary['predictions']} תחזיות!")


def screen_accuracy():
    st.title("🎯 דיוק המודל")
    st.subheader("ביצועי Backtest (מונדיאלים 2010–2022)")
    c1, c2, c3 = st.columns(3)
    c1.metric("Log-loss", "0.991", "טוב מ-1.099 (אקראי)")
    c2.metric("דיוק זוכה", "54.3%", "מעל 33% (אקראי)")
    c3.metric("תוצאה מדויקת", "9.8%")

    st.subheader("תחזיות שמורות מול תוצאות בפועל")
    rows = services.saved_predictions_vs_actual()
    if not rows:
        st.info("עדיין אין תחזיות שמורות. הן ייצברו עם תחילת הטורניר.")
        return
    hits = 0
    table = []
    for r in rows:
        actual = ("1" if r["home_goals"] > r["away_goals"]
                  else "2" if r["home_goals"] < r["away_goals"] else "X")
        pred = max((("1", r["p_home"]), ("X", r["p_draw"]), ("2", r["p_away"])),
                   key=lambda x: x[1])[0]
        hit = pred == actual
        hits += hit
        table.append({"משחק": f"{r['home']} - {r['away']}",
                      "חזוי": r["likely_score"], "בפועל": f"{r['home_goals']}-{r['away_goals']}",
                      "מנצח חזוי": pred, "בפועל ": actual, "✓": "✓" if hit else ""})
    st.metric("דיוק מצטבר", f"{hits/len(rows)*100:.1f}%", f"{hits}/{len(rows)} משחקים")
    st.dataframe(table, use_container_width=True, hide_index=True)


SCREENS = {
    "🏠 דשבורד": screen_dashboard,
    "⚽ תחזית משחק": screen_match,
    "📊 בתים": screen_groups,
    "🏆 נוקאאוט": screen_knockout,
    "👟 מלך שערים": screen_scorers,
    "👤 פרופיל נבחרת": screen_team,
    "✍️ הזנה ידנית": screen_manual,
    "🎯 דיוק המודל": screen_accuracy,
}


def main():
    ensure_initialized()   # בונה את הנתונים בהרצה ראשונה (חשוב לענן)
    st.sidebar.title("מונדיאל 2026 ⚽")
    choice = st.sidebar.radio("ניווט", list(SCREENS.keys()))
    st.sidebar.divider()

    # מצב מקור הנתונים + רענון
    if services.api_connected():
        st.sidebar.success("🟢 API-Football מחובר")
    else:
        st.sidebar.info("⚪ מצב נתונים פתוחים (ללא API)")
    if st.sidebar.button("🔄 רענן נתונים עכשיו"):
        with st.spinner("מושך תוצאות, פציעות ומעדכן הכול..."):
            summary = update.full_refresh()
        st.cache_data.clear()
        st.cache_resource.clear()
        st.sidebar.success(
            f"עודכן! פציעות: {summary.get('injuries', 0)}, "
            f"תחזיות: {summary.get('predictions', 0)}")
    st.sidebar.caption("Elo + Dixon-Coles · נתונים פתוחים + API אופציונלי")

    SCREENS[choice]()


main()
