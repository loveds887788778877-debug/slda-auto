@echo off
chcp 65001 > nul
title 슬다 채널 인증

cd /d "C:\Users\MYCOM\Desktop\제코자동화"
python auth_setup.py
pause
