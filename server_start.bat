@echo off
title AI Utrzymanie Ruchu - Serwer Aplikacji
color 0A
echo.
echo ====================================================
echo   INICJALIZACJA SERWERA: AI KATEGORYZACJA AWARII
echo ====================================================
echo.
echo Trwa uruchamianie interfejsu Streamlit i ladowanie modeli AI...
echo Prosze czekac, to moze potrwac kilkadziesiat sekund.
echo Prosze nie zamykac tego okna (minimalizacja na pasek zadan nie wplywa na prace).
echo.

:: 1. Aktywacja przenosnego srodowiska Python (zostawiamy zgodnie z Twoim wczesniejszym plikiem)
call "W_python-3.10.8.amd64\scripts\env.bat"

echo Aplikacja za chwile bedzie dostepna dla zespolu pod adresem:
echo.

:: 2. Wyciagniecie i wyswietlenie lokalnego IP na ekran
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address" /c:"Adres IPv4"') do echo  ---  %%a:8000  ---

echo.
echo ====================================================
echo.

:: 3. Glowna komenda uruchamiajaca aplikacje STREAMLIT w trybie publicznym
python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0

pause