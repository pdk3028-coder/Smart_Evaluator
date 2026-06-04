@echo off
chcp 65001 > nul
title Smart Evaluator Start System
echo ===================================================
echo   Smart Evaluator Start Script
echo ===================================================
echo.

REM Move to batch file directory
cd /d "%~dp0"

echo [1/3] Starting backend FastAPI server...
start "Smart Evaluator Backend" cmd /k "cd backend && python main.py"

echo.
echo [2/3] Starting frontend React/Vite server...
start "Smart Evaluator Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo [3/3] Waiting for servers to load (3 seconds)...
timeout /t 3 /nobreak > nul

echo.
echo Opening browser...
start http://localhost:5173

echo.
echo ===================================================
echo   Server started and browser opened successfully
echo   - Backend: http://localhost:8000
echo   - Frontend: http://localhost:5173
echo ===================================================
echo.
pause
