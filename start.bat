@echo off
setlocal EnableDelayedExpansion
title Watson's Stream Manager
color 0B

cd "C:\WatsonMcBot"

call venv\Scripts\activate

if exist "logs" (
    del /F /Q "logs\*.*" > nul 2>&1
) else (
    mkdir logs
)

python run_bot.py

exit