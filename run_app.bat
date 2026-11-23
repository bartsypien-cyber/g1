@echo off
echo Uruchamianie Inteligentnego Asystenta Utrzymania Ruchu...
echo Prosze czekac, ladowanie modeli AI moze potrwac kilkadziesiat sekund.
call "W_python-3.10.8.amd64\scripts\env.bat"
python -m streamlit run app.py
pause