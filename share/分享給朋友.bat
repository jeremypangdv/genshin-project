@echo off
chcp 65001 >nul
title Freminet Chat - 分享
cd /d "%~dp0.."
set PY=python
if exist "GPT-SoVITS\runtime\python.exe" set PY=GPT-SoVITS\runtime\python.exe
%PY% share\share.py
pause
