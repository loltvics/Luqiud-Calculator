@echo off
title Liquid Calculator - local server
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
python app.py
pause
