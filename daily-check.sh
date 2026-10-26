#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
echo '=== Phone must show as "device" below ==='
adb devices
pytest --clean-alluredir
TODAY=$(date +%F)
allure generate allure-results -o "reports/$TODAY" --clean --single-file
open "reports/$TODAY/index.html" 2>/dev/null || xdg-open "reports/$TODAY/index.html"
