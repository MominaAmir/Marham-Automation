"""Doctor app ADDS A LEAVE -> the patient app must stop offering that day -> the leave is deleted again.
                                                                     pytest -m doctor_leave -s
Leave day = the day after tomorrow (phone time). Reason typed: REASON (so the leave is easy to recognise).
Test 1 (DLV-01..08): leave for ALL LOCATIONS  -> no Video Consultation and no 13-b Hospital slots that day.
Test 2 (DLV-09..14): leave for 13-b Hospital only -> 13-b gone that day, Video Consultation still offered.
Clean-up ALWAYS runs (also after a failure) and deletes ONLY the leave cards this test added.
If the clean-up itself fails, reports/MANUAL_CLEANUP_NEEDED.txt says which leave to delete by hand.
Refuses to start if a leave already exists on the leave day (it would not know which leave is its own)."""
import contextlib
import datetime
from pathlib import Path

import allure
import pytest

from doctor_test_data import DOCTOR_LOCATIONS, VIDEO
from pages.doctor_home_page import DoctorHomePage
from pages.doctor_leave_pages import (ALL_LOCATIONS, CREATED, DELETED, AddLeavePage, LeavesPage, card_range, said,
                                      shown_date)
from pages.doctor_profile_tab_page import DoctorProfileTabPage
from utils.doctor_app import to_doctor_app
from utils.doctor_safety import check_doctor
from utils.patient_slots import chip_desc, offered_slots
from utils.steps import step

pytestmark = [pytest.mark.doctor_app, pytest.mark.doctor_leave]

REASON = "Automation test leave"
CLINIC = next(p for p in DOCTOR_LOCATIONS if p != VIDEO)            # 13-b Hospital
PLACES = (VIDEO, CLINIC)
CLEANUP_FILE = Path(__file__).resolve().parent.parent / "reports" / "MANUAL_CLEANUP_NEEDED.txt"


def _note(text, name):
    allure.attach(str(text), name=name, attachment_type=allure.attachment_type.TEXT)


def _days(driver):
    """(tomorrow, leave day = day after tomorrow) from the phone's clock."""
    now = datetime.datetime.strptime(driver.get_device_time("YYYY-MM-DD HH:mm"), "%Y-%m-%d %H:%M")
    midnight = datetime.datetime.combine(now.date(), datetime.time())
    print(f"\nPHONE TIME {now:%a %d %b %I:%M %p}")
    return midnight + datetime.timedelta(days=1), midnight + datetime.timedelta(days=2)


@contextlib.contextmanager
def _soft(failures, label):
    """A failed check is recorded and the test goes on (the clean-up must still run)."""
    try:
        yield
    except AssertionError as exc:
        failures.append(f"{label}: {exc}")


def _leaves_page(driver):
    """Fresh doctor app -> Profile tab -> Manage Leaves."""
    to_doctor_app(driver)
    home = DoctorHomePage(driver)
    assert home.is_loaded(), "Doctor home ('Overview') did not load"
    check_doctor(home.doctor_name())
    tab = DoctorProfileTabPage(driver)
    assert tab.open(), "Profile tab did not open"
    tab.open_row("Manage Leaves")
    page = LeavesPage(driver)
    assert page.is_open(), "Manage Leaves did not open"
    return page


def _leaves_on(driver, day):
    leaves = _leaves_page(driver).leaves()
    _note("\n".join(l.label() for l in leaves) or "no leaves", f"Manage Leaves ({day:%d %b})")
    return [l for l in leaves if l.covers(day)]


def _no_leave_yet(driver, day):
    existing = _leaves_on(driver, day)
    assert not existing, (f"A leave already exists on {day:%a %d %b} - delete it by hand or run another day "
                          f"(the test only deletes leaves it added): " + "; ".join(l.label() for l in existing))


def _add_leave(driver, location, day):
    page = _leaves_page(driver)
    page.open_add()
    form = AddLeavePage(driver)
    assert form.is_open(), "Add Leave did not open"
    _note(form.options(), "Add Leave location options")
    form.choose_location(location)
    form.pick_date(0, day)
    form.pick_date(1, day)
    shown = form.shown_dates()
    assert shown == [shown_date(day)] * 2, f"Start / End Date show {shown}, expected '{shown_date(day)}' twice"
    form.type_reason(REASON)
    assert form.reason() == REASON, f"Reason box shows '{form.reason()}', expected '{REASON}'"
    found = form.save()
    _note(found or "nothing", f"after Save Leave ({location}, {day:%d %b})")
    assert said(found, CREATED), f"No '{CREATED}' after Save Leave: {found}"


def _check_cards(driver, day, places):
    ours = _leaves_on(driver, day)
    shown = sorted(l.location for l in ours)
    assert shown == sorted(places), f"Manage Leaves: leave cards for {day:%d %b} are {shown}, expected {sorted(places)}"
    for leave in ours:
        problems = []
        if leave.start != day.date() or leave.end != day.date():
            problems.append(f"dates {leave.start:%d %b %Y} - {leave.end:%d %b %Y}, expected '{card_range(day)}'")
        if leave.reason != REASON:
            problems.append(f"reason '{leave.reason}', expected '{REASON}'")
        assert not problems, f"Leave card {leave.location}: " + "; ".join(problems)


def _delete_leaves(driver, day):
    """Delete every leave card on the leave day (all were added by this test: checked before adding)."""
    problems = []
    for _ in range(2 * len(PLACES) + 1):                       # one card at a time; a few extra tries
        ours = _leaves_on(driver, day)
        if not ours:
            return problems
        page = LeavesPage(driver)
        try:
            found = page.delete(ours[0])
            _note(found or "nothing", f"after DELETE ({ours[0].label()})")
            if not said(found, DELETED):
                problems.append(f"no '{DELETED}' after deleting {ours[0].label()}: {found}")
        except AssertionError as exc:
            problems.append(str(exc))
    left = _leaves_on(driver, day)
    return problems + [f"Manage Leaves: delete the leave by hand: {l.label()}" for l in left]


def _cleanup(driver, day):
    problems = _delete_leaves(driver, day)
    left = [p for p in problems if p.startswith("Manage Leaves")]
    if left:
        CLEANUP_FILE.parent.mkdir(exist_ok=True)
        with CLEANUP_FILE.open("a", encoding="utf-8") as f:
            for p in left:
                f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M}  DOCTOR APP - {p}\n")
    assert not left, "CLEAN-UP FAILED - delete by hand:\n" + "\n".join(left)
    assert not problems, "Leaves deleted, but: " + "; ".join(problems)


def _patient(driver, place, days):
    """{day: offered?} in the patient app's Booking Summary of place (date chip present AND slots shown)."""
    _fee, chips, offered = offered_slots(driver, place, days, max_swipes=1)
    _note(f"date chips: {chips}\n" + "\n".join(f"{d:%a %d %b}: {', '.join(f'{t:%I:%M %p}' for t in (s or [])) or 'none'}"
                                              for d, s in offered.items()), f"patient app - {place}")
    return {d: chip_desc(d) in chips and bool(offered[d]) for d in days}


def _patient_offers(driver, place, day, expected, why):
    shown = _patient(driver, place, [day])[day]
    assert shown == expected, (f"{why}: patient app ({place}) {'offers' if shown else 'does not offer'} "
                               f"{day:%a %d %b}, expected it {'offered' if expected else 'gone'}")


def _patient_hides(driver, place, tomorrow, day):
    shown = _patient(driver, place, [tomorrow, day])
    assert not shown[day], f"Leave on {day:%a %d %b}, but the patient app ({place}) still offers that day"
    assert shown[tomorrow], f"Leave only on {day:%a %d %b}, but the patient app ({place}) has no slots {tomorrow:%a %d %b} either"


@pytest.mark.flaky(reruns=0)
@allure.title("DLV: leave for all locations -> patient app hides that day (Video + clinic) -> leave deleted")
def test_leave_all_locations_reaches_patient_app(driver):
    tomorrow, day = _days(driver)
    print(f"Leave day {day:%a %d %b} | all locations | reason '{REASON}'")
    failures, added = [], False
    with step("DLV-01"):
        _no_leave_yet(driver, day)
    with step("DLV-02"):
        for place in PLACES:
            _patient_offers(driver, place, day, True, "Before the leave")
    try:
        with step("DLV-03"):
            added = True                                  # also when Save fails half-way: clean-up checks the list
            _add_leave(driver, ALL_LOCATIONS, day)
        with _soft(failures, "DLV-04"), step("DLV-04"):
            _check_cards(driver, day, PLACES)
        with _soft(failures, "DLV-05"), step("DLV-05"):
            _patient_hides(driver, VIDEO, tomorrow, day)
        with _soft(failures, "DLV-06"), step("DLV-06"):
            _patient_hides(driver, CLINIC, tomorrow, day)
    finally:
        if added:
            with step("DLV-07"):
                _cleanup(driver, day)
    with _soft(failures, "DLV-08"), step("DLV-08"):
        for place in PLACES:
            _patient_offers(driver, place, day, True, "Leave deleted")
    to_doctor_app(driver)
    assert not failures, "The patient app did not follow the doctor's leave:\n" + "\n".join(failures)


@pytest.mark.flaky(reruns=0)
@allure.title("DLV: leave for one clinic only -> only that clinic's slots disappear -> leave deleted")
def test_leave_one_location_only(driver):
    tomorrow, day = _days(driver)
    print(f"Leave day {day:%a %d %b} | {CLINIC} only | reason '{REASON}'")
    failures, added = [], False
    try:
        with step("DLV-09"):
            _no_leave_yet(driver, day)
            _patient_offers(driver, CLINIC, day, True, "Before the leave")
            added = True
            _add_leave(driver, CLINIC, day)
        with _soft(failures, "DLV-10"), step("DLV-10"):
            _check_cards(driver, day, [CLINIC])
        with _soft(failures, "DLV-11"), step("DLV-11"):
            _patient_hides(driver, CLINIC, tomorrow, day)
        with _soft(failures, "DLV-12"), step("DLV-12"):
            _patient_offers(driver, VIDEO, day, True, f"Leave only for {CLINIC}")
    finally:
        if added:
            with step("DLV-13"):
                _cleanup(driver, day)
    with _soft(failures, "DLV-14"), step("DLV-14"):
        _patient_offers(driver, CLINIC, day, True, "Leave deleted")
    to_doctor_app(driver)
    assert not failures, "The patient app did not follow the doctor's leave:\n" + "\n".join(failures)