@echo off
setlocal
cd /d "%~dp0.."
conda run --no-capture-output -n ciencia-de-datos python "Pipeline\etl_victimizacion.py" %*
endlocal
