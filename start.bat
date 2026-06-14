@echo off
echo ============================================
echo   NotulaAI — BPPK PUSDIKLAT KP
echo   Server: http://localhost:8000
echo ============================================
echo.
echo Buka browser ke: http://localhost:8000
echo (Jangan buka index.html langsung!)
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 600 --ws-max-size 2147483648 --loop asyncio --h11-max-incomplete-event-size 10485760
pause