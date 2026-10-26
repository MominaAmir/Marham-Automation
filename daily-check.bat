@echo off
cd /d %~dp0
call .venv\Scripts\activate
echo === Phone must show as "device" below ===
adb devices
pytest --clean-alluredir
for /f %%i in ('python -c "import datetime;print(datetime.date.today())"') do set TODAY=%%i
call allure generate allure-results -o reports\%TODAY% --clean --single-file
start "" reports\%TODAY%\index.html
pause
