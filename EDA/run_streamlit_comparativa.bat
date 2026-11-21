@echo off
setlocal
cd /d "%~dp0"
conda run --no-capture-output -n ciencia-de-datos streamlit run app_comparativa_eda.py
endlocal
