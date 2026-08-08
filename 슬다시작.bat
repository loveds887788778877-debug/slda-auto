@echo off
chcp 65001 > nul
title 슬다 자동화 v10

echo.
echo  ⚡ 슬다 자동화 v10 시작!
echo  ─────────────────────────────
echo.

cd /d "C:\Users\MYCOM\Desktop\제코자동화"

:: pip 자동 설치
echo  📦 라이브러리 설치 중...
pip install flask gtts google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client --quiet

echo  ✅ 설치 완료!
echo.
echo  🌐 브라우저에서 열기: http://localhost:5000
echo.

:: 자동으로 브라우저 열기 (3초 후)
start /b cmd /c "timeout /t 3 /nobreak > nul && start http://localhost:5000"

:: 앱 시작
python app.py

pause
