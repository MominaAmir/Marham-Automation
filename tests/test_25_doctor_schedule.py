"""Doctor app CHANGES the schedule -> the patient app must follow -> everything is put back.
                                                                     pytest -m doctor_schedule -s
1. Scheduler Settings (Video Consultation): slot length 10 -> 15 min, Save -> patient Booking Summary uses 15 min.
2. Hospital Details (Video Consultation): switch OFF the day after tomorrow, Save -> patient app no longer offers it.
3. Clean-up (ALWAYS, also after a failure): day back ON, slot length back to 10 min -> patient app back to normal.
If the clean-up itself fails, reports/MANUAL_CLEANUP_NEEDED.txt says exactly what to set back by hand."""
import contextlib
import datetime
from pathlib import Path

import allure
import pytest

from doctor_test_data import DOCTOR_SLOT_MINUTES, VIDEO
from pages.doctor_home_page import DoctorHomePage
from pages.doctor_practice_pages import DAYS, HospitalDetailsPage, ManageLocationsPage, SchedulerSettingsPage
from pages.doctor_profile_tab_page import DoctorProfileTabPage
from utils.doctor_app import to_doctor_app
from utils.doctor_safety import check_doctor
from utils.patient_slots import chip_desc, offered_slots
from utils.steps import step

pytestmark = [pytest.mark.doctor_app, pytest.mark.doctor_schedule]

ORIGINAL_MINUTES = DOCTOR_SLOT_MINUTES[VIDEO]                      # 10
TEST_MINUTES = 15 if ORIGINAL_MINUTES != 15 else 20
SAVED_MESSAGE = "Scheduler settings updated"
CLEANUP_FILE = Path(__file__).resolve().parent.parent / "reports" / "MANUAL_CLEANUP_NEEDED.txt"


def _note(text, name):
    allure.attach(str(text), name=name, attachment_type=allure.attachment_type.TEXT)


def _device_now(driver):
    return datetime.datetime.strptime(driver.get_device_time("YYYY-MM-DD HH:mm"), "%Y-%m-%d %H:%M")


def _profile_row(driver, row):
    """Fresh doctor app -> Profile tab -> row (a fresh start each time: no doubt about which screen we are on)."""
    to_doctor_app(driver)
    home = DoctorHomePage(driver)
    assert home.is_loaded(), "Doctor home ('Overview') did not load"
    check_doctor(home.doctor_name())
    tab = DoctorProfileTabPage(driver)
    assert tab.open(), "Profile tab did not open"
    tab.open_row(row)


def _scheduler(driver):
    _profile_row(driver, "Scheduler Settings")
    page = SchedulerSettingsPage(driver)
    assert page.is_open(), "Scheduler Settings did not open"
    page.choose_location(VIDEO)
    assert page.options().get(VIDEO), f"'{VIDEO}' option did not become selected"
    return page


def _video_details(driver):
    _profile_row(driver, "Manage Locations")
    locations = ManageLocationsPage(driver)
    assert locations.is_open(), "Manage Locations did not open"
    locations.open_location(VIDEO)
    details = HospitalDetailsPage(driver)
    assert details.is_open(), f"Hospital Details did not open for {VIDEO}"
    return details


def _set_minutes(driver, minutes):
    page = _scheduler(driver)
    page.choose_minutes(minutes)
    said = page.save()
    _note(said or "nothing", f"after saving {minutes} min")
    assert any(SAVED_MESSAGE in t for t in said), f"No '{SAVED_MESSAGE}' after saving {minutes} min: {said}"
    page = _scheduler(driver)                                      # open again: was it really saved?
    shown, shares = page.slot_minutes()
    _note(f"{shown} min ({shares})", f"Scheduler Settings after saving {minutes} min")
    assert shown in (None, minutes), f"Saved {minutes} min, Scheduler Settings now shows {shown} min ({shares})"


def _set_day(driver, weekday, on):
    """Switch the weekday chip of the video slot ON/OFF (only taps when it is not already like that)."""
    details = _video_details(driver)
    _boxes, selected = details.day_chips()
    if selected is not None and selected[weekday] == on:
        return []
    details.toggle_day(weekday)
    _boxes, selected = details.day_chips()
    assert selected is None or selected[weekday] == on, \
        f"{DAYS[weekday]} chip did not turn {'ON' if on else 'OFF'} when tapped"
    said = details.save()
    _note(said or "nothing", f"after saving {DAYS[weekday]} {'ON' if on else 'OFF'}")
    return said


@contextlib.contextmanager
def _soft(failures, label):
    """A failed patient-side check is recorded and the test goes on (the clean-up must still run)."""
    try:
        yield
    except AssertionError as exc:
        failures.append(f"{label}: {exc}")


def _grid_problems(slots, minutes):
    if not slots or len(slots) < 3:
        return [f"only {len(slots or [])} slots to compare"]
    gaps = sorted({int((b - a).total_seconds() // 60) for a, b in zip(slots, slots[1:])})
    return [] if gaps[0] == minutes else [f"slots are {gaps[0]} min apart, expected {minutes} min "
                                          f"({', '.join(f'{t:%I:%M %p}' for t in slots[:6])} ...)"]


@pytest.mark.flaky(reruns=0)
@allure.title("DSCH: slot length and working day changed in the doctor app -> patient app follows -> restored")
def test_schedule_changes_reach_patient_app(driver):
    now = _device_now(driver)
    tomorrow = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time())
    day_off = datetime.datetime.combine(now.date() + datetime.timedelta(days=2), datetime.time())
    weekday = day_off.weekday()
    changed = {"minutes": False, "day": False}
    failures = []                                     # patient-side checks: recorded, the test goes on
    print(f"\nPHONE TIME {now:%a %d %b %I:%M %p} | slot length {ORIGINAL_MINUTES} -> {TEST_MINUTES} min | "
          f"day switched off: {day_off:%a %d %b}")

    def patient_uses_test_minutes():
        _fee, _chips, offered = offered_slots(driver, VIDEO, [tomorrow], max_swipes=1)
        slots = offered[tomorrow]
        _note(", ".join(f"{t:%I:%M %p}" for t in slots or []) or "none", f"patient slots {tomorrow:%a %d %b} ({TEST_MINUTES} min)")
        problems = _grid_problems(slots, TEST_MINUTES)
        assert not problems, f"Doctor saved {TEST_MINUTES} min, patient app {tomorrow:%a %d %b}: {problems[0]}"

    def patient_hides_day_off():
        _fee, chips, offered = offered_slots(driver, VIDEO, [day_off], max_swipes=1)
        _note(f"date chips: {chips}; slots: {offered[day_off]}", f"patient app with {DAYS[weekday]} OFF")
        assert chip_desc(day_off) not in chips and not offered[day_off], \
            f"{DAYS[weekday]} is OFF in the doctor app, but the patient app still offers {day_off:%a %d %b}: {chips}"

    try:
        with step("DSCH-01"):
            page = _scheduler(driver)
            shown, shares = page.slot_minutes()
            _note(f"{shown} min ({shares})", "slot length before")
            assert shown in (None, ORIGINAL_MINUTES), \
                f"Video slot length is {shown} min before the test, expected {ORIGINAL_MINUTES} (fix it first)"
            changed["minutes"] = True
            _set_minutes(driver, TEST_MINUTES)

        with _soft(failures, "DSCH-02"), step("DSCH-02"):
            patient_uses_test_minutes()

        with step("DSCH-03"):
            details = _video_details(driver)
            _boxes, selected = details.day_chips()
            assert selected is None or selected[weekday], \
                f"{DAYS[weekday]} is already OFF for {VIDEO} before the test (fix it first)"
            changed["day"] = True
            _set_day(driver, weekday, on=False)

        with _soft(failures, "DSCH-04"), step("DSCH-04"):
            patient_hides_day_off()

    finally:
        with step("DSCH-05"):
            problems = []
            if changed["day"]:
                try:
                    _set_day(driver, weekday, on=True)
                    changed["day"] = False
                except Exception as exc:              # keep going: the slot length must be restored too
                    problems.append(f"Video Consultation > Hospital Details: switch {DAYS[weekday]} back ON ({exc!r})")
            if changed["minutes"]:
                try:
                    _set_minutes(driver, ORIGINAL_MINUTES)
                    changed["minutes"] = False
                except Exception as exc:
                    problems.append(f"Scheduler Settings > Video Consultation: set {ORIGINAL_MINUTES} min again ({exc!r})")
            if problems:
                CLEANUP_FILE.parent.mkdir(exist_ok=True)
                with CLEANUP_FILE.open("a", encoding="utf-8") as f:
                    for p in problems:
                        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M}  DOCTOR APP - set back by hand: {p}\n")
            assert not problems, "CLEAN-UP FAILED - set back by hand:\n" + "\n".join(problems)

    def patient_back_to_normal():
        _fee, chips, offered = offered_slots(driver, VIDEO, [tomorrow, day_off], max_swipes=1)
        _note(f"date chips: {chips}", "patient app after the clean-up")
        assert offered[day_off], f"{day_off:%a %d %b} is back ON, but the patient app offers no slots that day"
        problems = _grid_problems(offered[tomorrow], ORIGINAL_MINUTES)
        assert not problems, f"Slot length back to {ORIGINAL_MINUTES} min, patient app: {problems[0]}"

    with _soft(failures, "DSCH-06"), step("DSCH-06"):
        patient_back_to_normal()
    to_doctor_app(driver)
    assert not failures, "The patient app did not follow the doctor's changes:\n" + "\n".join(failures)