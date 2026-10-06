@echo off
title Automeris ML - Uji Bending
cd /d "%~dp0"
echo Menyiapkan library (hanya lama saat pertama kali)...
python -m pip install -q -r requirements.txt
echo Membuka aplikasi di browser...
python -m streamlit run app.py
pause
