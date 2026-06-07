@echo off
chcp 65001 >nul
cd /d "C:\claude\מונדיאל"
echo ============================================
echo   פותח את מערכת חיזוי המונדיאל...
echo   הדפדפן ייפתח אוטומטית. אל תסגור חלון זה.
echo   לסגירת התוכנה: סגור חלון זה.
echo ============================================
".venv\Scripts\python.exe" -m streamlit run "app\dashboard.py"
pause
