"""pytest runs this automatically. It starts Appium, opens a fresh app session for every test
(the DOCTOR app for tests marked doctor_app, otherwise the patient app), attaches a screenshot +
screen XML on failure, cleans up left-over PC bookings, and prints which test_cases*.csv steps
passed, failed or were never reached."""
import csv
import datetime
import socket
from pathlib import Path
import urllib.request
import allure
import pytest
from appium import webdriver
from appium.webdriver.appium_service import AppiumService
import os
import subprocess
import urllib.request
from config.capabilities import android_options
from pages.appointments_page import AppointmentsPage
from pages.base_page import BasePage
from test_data import APP_ACTIVITY, APP_PACKAGE, DOCTOR_NAME
from utils import adb, steps
from utils.app import restart_app

APPIUM_HOST, APPIUM_PORT = "127.0.0.1", 4723
APPIUM_URL = f"http://{APPIUM_HOST}:{APPIUM_PORT}"
REPORTS = Path(__file__).parent / "reports"
CLEANUP_FILE = REPORTS / "MANUAL_CLEANUP_NEEDED.txt"
_preflight_failed = {"patient": False, "doctor": False}


def _app(item):
    return "doctor" if item.get_closest_marker("doctor_app") else "patient"


def _is_preflight(item):
    return bool(item.get_closest_marker("preflight") or item.get_closest_marker("doctor_preflight"))


# ---------- guards that stop a run early with a clear message ----------
def pytest_sessionstart(session):
    REPORTS.mkdir(exist_ok=True)


def _port_in_use():
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex((APPIUM_HOST, APPIUM_PORT)) == 0

def _appium_running():
    """True if an Appium server already answers on 127.0.0.1:4723 (e.g. one you started by hand)."""
    try:
        with urllib.request.urlopen(f"{APPIUM_URL}/status", timeout=3) as answer:
            return answer.status == 200
    except Exception:
        return False


# ---------- Appium server and driver ----------
@pytest.fixture(scope="session")
def appium_server():
    if "REPLACE" in APP_PACKAGE or "REPLACE" in APP_ACTIVITY:
        pytest.exit("Fill in APP_PACKAGE and APP_ACTIVITY in test_data.py first (Step 3.4).", returncode=4)
    problem = _phone_problem()
    if problem:
        pytest.exit(f"{problem}. Reconnect the phone (USB recommended), check with  adb devices  and run again.",
                    returncode=4)
    if _appium_running():                       # you started Appium yourself: use it (its window shows the log)
        yield None
        return
    if _port_in_use():
        pytest.exit("Port 4723 is busy but Appium is not answering there: close old 'appium'/'node' windows "
                    "and Appium Inspector, then run again.", returncode=4)
    server = AppiumService()
    server.start(args=["--address", APPIUM_HOST, "-p", str(APPIUM_PORT),
                       "--log", str(REPORTS / "appium.log"), "--log-timestamp"],
                 timeout_ms=120000)             # slow laptops need more than 60 s
    yield server
    server.stop()

@pytest.fixture
def driver(appium_server, request):
    """A new app session for every test, starting on the home screen of the right app."""
    if request.node.get_closest_marker("doctor_app"):
        from utils.doctor_app import check_doctor_app_settings, doctor_options, restart_doctor_app
        check_doctor_app_settings()
        drv = webdriver.Remote(APPIUM_URL, options=doctor_options())
        restart_doctor_app(drv)
    else:
        drv = webdriver.Remote(APPIUM_URL, options=android_options())
        restart_app(drv)
    BasePage(drv).dismiss_popups()
    yield drv
    try:
        drv.quit()
    except Exception:
        pass


# ---------- PC safety net: never leave a test booking active ----------
@pytest.fixture
def pc_booking(driver):
    """The PC test sets state['active'] = True after booking and False after cancelling."""
    state = {"active": False}
    yield state
    if not state["active"]:
        return
    try:
        restart_app(driver)
        page = AppointmentsPage(driver)
        page.open()
        page.cancel_booking(DOCTOR_NAME)
        allure.attach("The test failed after booking; clean-up cancelled the booking.",
                      name="clean-up", attachment_type=allure.attachment_type.TEXT)
    except Exception as exc:
        with CLEANUP_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M}  Cancel the PC test booking with "
                    f"{DOCTOR_NAME} by hand. Auto clean-up failed: {exc!r}\n")


# ---------- failure evidence + skip an app's tests if its preflight failed ----------
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when in ("setup", "call") and report.failed:
        drv = item.funcargs.get("driver")
        if drv:
            try:
                allure.attach(drv.get_screenshot_as_png(), name="screenshot",
                              attachment_type=allure.attachment_type.PNG)
                allure.attach(drv.page_source, name="screen XML (use to fix locators)",
                              attachment_type=allure.attachment_type.XML)
            except Exception:
                pass
    if _is_preflight(item) and report.when in ("setup", "call"):
        if report.failed:
            _preflight_failed[_app(item)] = True
        elif report.when == "call" and report.passed:
            _preflight_failed[_app(item)] = False   # passed on its retry


def pytest_runtest_setup(item):
    if _is_preflight(item) or item.get_closest_marker("doctor_login"):
        return
    if _preflight_failed[_app(item)] and "driver" in item.fixturenames:
        which = "DPRE" if _app(item) == "doctor" else "PRE"
        pytest.skip(f"Preflight failed: fix the phone/app/login problem first (see the {which} test).")


# ---------- step coverage summary and Allure environment ----------
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not steps.STARTED:
        return
    flows_run = {sid.split("-")[0] for sid in steps.STARTED}
    rows = []
    for row in steps.load_cases():
        sid = row["step_id"].strip()
        if not steps.is_automated(row) or sid.split("-")[0] not in flows_run:
            continue
        result = "passed" if sid in steps.PASSED else "FAILED" if sid in steps.STARTED else "NOT REACHED"
        rows.append((sid, row["flow"], row["step"], result))

    out = REPORTS / f"step-coverage-{datetime.date.today():%Y-%m-%d}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["step_id", "flow", "step", "result"])
        w.writerows(rows)

    tr = terminalreporter
    passed = sum(1 for r in rows if r[3] == "passed")
    tr.write_sep("=", f"STEP COVERAGE: {passed}/{len(rows)} steps passed  (saved to {out.name})")
    for sid, flow, step_name, result in rows:
        if result != "passed":
            tr.write_line(f"  {result:<12} {sid:<9} {step_name}")
    if CLEANUP_FILE.exists():
        tr.write_sep("!", f"MANUAL CLEAN-UP NEEDED: read {CLEANUP_FILE}")


def pytest_sessionfinish(session, exitstatus):
    alluredir = session.config.getoption("--alluredir", default=None)
    if not alluredir or not steps.STARTED:
        return
    info = {"app_package": APP_PACKAGE, "app_version": adb.app_version(APP_PACKAGE), **adb.device_info()}
    try:
        from doctor_test_data import DOCTOR_APP_PACKAGE
        if "REPLACE" not in DOCTOR_APP_PACKAGE:
            info["doctor_app_package"] = DOCTOR_APP_PACKAGE
            info["doctor_app_version"] = adb.app_version(DOCTOR_APP_PACKAGE)
    except ImportError:
        pass
    Path(alluredir).mkdir(parents=True, exist_ok=True)
    with (Path(alluredir) / "environment.properties").open("w", encoding="utf-8") as f:
        for key, value in info.items():
            f.write(f"{key}={value}\n")

def _phone_problem():
    """'' if the phone is connected AND answering, otherwise what is wrong."""
    try:
        out = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return "adb did not answer (is it installed / on PATH?)"
    rows = [line.split() for line in out.splitlines()[1:] if line.strip()]
    wanted = os.environ.get("ANDROID_UDID")
    if wanted:
        rows = [r for r in rows if r[0] == wanted]
    ready = [r[0] for r in rows if len(r) > 1 and r[1] == "device"]
    if not ready:
        shown = ", ".join(" ".join(r) for r in rows) or "no phone listed"
        return f"phone not ready ({shown})"
    if len(ready) > 1 and not wanted:
        return f"more than one phone/connection listed ({', '.join(ready)}): unplug one or run  adb disconnect"
    try:                                           # listed is not enough: it must also answer
        answer = subprocess.run(["adb", "-s", ready[0], "shell", "getprop", "ro.build.version.sdk"],
                                capture_output=True, text=True, timeout=15).stdout.strip()
    except subprocess.TimeoutExpired:
        answer = ""
    return "" if answer.isdigit() else f"phone {ready[0]} is listed but not answering (Wi-Fi dropped?)"