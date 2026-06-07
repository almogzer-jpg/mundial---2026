# מערכת חיזוי מונדיאל 2026 ⚽

כלי אישי לחיזוי תוצאות גביע העולם, מבוסס **נתונים פתוחים בלבד** (ללא הרשמה,
ללא מפתח, ללא תשלום) ומודל סטטיסטי: **Elo + Dixon-Coles Poisson**.

## מה המערכת נותנת
לכל משחק: הסתברות ניצחון/תיקו/הפסד, 5 תוצאות סבירות + תוצאה מדויקת,
תוחלת שערים, ורמת ביטחון (נמוכה/בינונית/גבוהה).
לטורניר: טבלאות בתים, עץ נוקאאוט, וסיכויי התקדמות/זכייה (Monte-Carlo).
מתעדכן אוטומטית עם הזנת כל תוצאה.

## הרצה מהירה
```powershell
# הפעלת סביבת העבודה
.\.venv\Scripts\Activate.ps1

# (פעם ראשונה / לרענון נתונים) — קליטה, Elo, ותחזיות
python -m scripts.refresh

# הפעלת הדשבורד
streamlit run app/dashboard.py
```
הדשבורד ייפתח בדפדפן (ברירת מחדל http://localhost:8501).

## מסכי הדשבורד
🏠 דשבורד · ⚽ תחזית משחק · 📊 בתים · 🏆 נוקאאוט · 👤 פרופיל נבחרת ·
✍️ הזנה ידנית · 🎯 דיוק המודל

## מבנה הפרויקט
```
config.py            הגדרות מרכזיות + פרמטרי מודל מכוילים
ingestion/
  providers/         שכבת ספקים אחידה (open_data, manual, base)
  names.py           נרמול שמות נבחרות
  loader.py          קליטה ומיזוג ל-SQLite
  api_football.py    ספק API עתידי (מושבת — לחיבור עתידי)
ratings/
  weights.py         משקלי חשיבות + עדכניות (דעיכה מעריכית)
  elo.py             מנוע Elo (World Football Elo)
prediction/
  strength.py        חוזקי התקפה/הגנה משוקללים
  poisson.py         מודל Dixon-Coles -> הסתברויות ותוצאות
  engine.py          הרכבת המודל
  backtest.py        בדיקה וכיול על מונדיאלים 2010-2022
tournament/
  standings.py       טבלאות + שוברי-שוויון פיפ"א
  bracket.py         בראקט 48 קבוצות -> שלב 32
  simulate.py        Monte-Carlo
app/                 דשבורד Streamlit (dashboard.py, services.py)
update.py            מתזמר העדכון המתגלגל
scripts/             refresh, ingest, build_ratings, predict_demo, simulate_demo
data/                mundial.db + cache + manual/overrides.json
docs/SPEC.md         מסמך אפיון
```

## ביצועי המודל (Backtest, מונדיאלים 2010–2022)
Log-loss **0.991** (אקראי=1.099) · דיוק זוכה **54.3%** · תוצאה מדויקת **9.8%**.

## מקורות הנתונים (פתוחים, חינמיים)
- `martj42/international_results` — ~49K תוצאות + לוח 2026
- `openfootball/world-cup` — שיוך הבתים
- Elo מחושב פנימית; הזנה ידנית כגיבוי

## חיבור API-Football (אופציונלי — תוצאות חיות + פציעות אוטומטיות)
המערכת עובדת בלי זה. לעדכון אוטומטי:
1. הירשם (חינם) ב-https://dashboard.api-football.com/register וקבל API Key.
2. העתק `.env.example` ל-`.env` ומלא `API_FOOTBALL_KEY=...`.
3. הפעל מחדש ולחץ "🔄 רענן נתונים עכשיו" בדשבורד.

כשמפתח מוגדר, ספק `APIFootballProvider` מצטרף אוטומטית למיזוג ומביא
תוצאות חיות, פציעות וסגלים. פציעות של שחקני-מפתח מורידות את סיכויי
הקבוצה (ראה `prediction/injuries.py` — רשימת שחקני המפתח ניתנת לעריכה).
ללא מפתח — המערכת ממשיכה בנתונים פתוחים + הזנה ידנית. אפס שינוי במודל/UI/DB.

### עדכון אוטומטי מתוזמן (רשות)
אפשר לתזמן רענון יומי ב-Windows Task Scheduler שיריץ:
`".venv\Scripts\python.exe" -m scripts.refresh` מתוך תיקיית הפרויקט.

## הערות
- תאריכים מוצגים בפורמט DD/MM/YYYY (תקן ישראלי).
- כל התחזיות נשמרות כ-snapshot למדידת דיוק מצטברת.
