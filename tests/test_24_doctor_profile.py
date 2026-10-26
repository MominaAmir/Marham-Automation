"""Doctor app - Profile, practice settings and the slots patients see. READ-ONLY.   pytest -m doctor_profile -s
Doctor app: Profile tab, View Profile, Manage Locations, Hospital Details (via Edit Location), Scheduler Settings,
Manage Leaves. Patient app: the test doctor's Booking Summary per location, today and tomorrow.
Never taps Save Changes, Add Slot, a switch, a day chip, a time box, Add New Location/Leave or Log Out.
(Scheduler Settings' location options are tapped only to SHOW each location's slot length; nothing is saved.)"""
import datetime

import allure
import pytest

from doctor_test_data import DOCTOR_LOCATIONS, DOCTOR_SLOT_MINUTES, VIDEO
from pages.doctor_home_page import DoctorHomePage
from pages.doctor_practice_pages import (DAYS, HospitalDetailsPage, ManageLeavesPage, ManageLocationsPage,
                                         SchedulerSettingsPage)
from pages.doctor_profile_tab_page import MENU, SECTIONS, DoctorProfileTabPage, ViewProfilePage
from utils.doctor_app import to_doctor_app
from utils.doctor_safety import check_doctor
from utils.patient_slots import offered_slots
from utils.screen_colour import Image
from utils.steps import step

pytestmark = [pytest.mark.doctor_app, pytest.mark.doctor_profile]

PROFILE_FIELDS = ("Full Name", "Email Address", "Phone Number", "PMDC Number", "Specialization", "Years of Experience")
EARLIEST_MINUTES = 15            # a slot today must be at least this far after the phone's time


def _note(text, name):
    allure.attach(str(text), name=name, attachment_type=allure.attachment_type.TEXT)


def _device_now(driver):
    return datetime.datetime.strptime(driver.get_device_time("YYYY-MM-DD HH:mm"), "%Y-%m-%d %H:%M")


def _hhmm(day, text):
    return datetime.datetime.combine(day, datetime.datetime.strptime(text, "%H:%M").time())


def _back_to_profile(driver, tab):
    for _ in range(3):
        if tab.is_visible(tab.TITLE, timeout=3):
            return
        driver.back()
    assert tab.is_visible(tab.TITLE, timeout=5), "Could not get back to the Profile tab"


def _check_day(day, slots, windows, minutes, now, leave_free):
    """Problems with one day's offered slots (empty list = all good)."""
    weekday = DAYS[day.weekday()]
    open_windows = [w for w in windows if w.days is None or weekday in w.days]
    if slots is None or not slots:                    # today may have no slots left late in the day
        return [] if not open_windows or not leave_free or day.date() == now.date() else [f"{day:%a %d %b}: no slots offered, "
                                                              f"but the doctor works {weekday} "
                                                              f"({', '.join(w.label() for w in open_windows)})"]
    problems = []
    if not open_windows:
        problems.append(f"{day:%a %d %b}: slots offered on a day the doctor does not work ({weekday})")
    for t in slots:
        inside = [w for w in open_windows if _hhmm(day, w.start) <= t < _hhmm(day, w.end)]
        if open_windows and not inside:
            problems.append(f"{t:%a %d %b %I:%M %p}: outside the consultation hours")
        elif inside and (t - _hhmm(day, inside[0].start)).seconds // 60 % minutes:
            problems.append(f"{t:%I:%M %p}: not on the {minutes}-minute grid from {inside[0].start}")
        if t.date() == now.date() and t < now + datetime.timedelta(minutes=EARLIEST_MINUTES):
            problems.append(f"{t:%I:%M %p} today: less than {EARLIEST_MINUTES} min after the phone's time {now:%I:%M %p}")
    gaps = sorted({int((b - a).total_seconds() // 60) for a, b in zip(slots, slots[1:])})
    if gaps and gaps[0] != minutes:
        problems.append(f"{day:%a %d %b}: slots are {gaps[0]} min apart, Scheduler Settings says {minutes} min")
    if day.date() != now.date() and leave_free and open_windows:
        first = min(_hhmm(day, w.start) for w in open_windows)
        if slots[0] != first:
            problems.append(f"{day:%a %d %b}: first slot {slots[0]:%I:%M %p}, the hours start at {first:%H:%M}")
    return problems


def _not_offered(day, slots, windows, minutes, now):
    """Grid times inside the hours that are NOT offered (normally: already booked). Today: only after the first slot."""
    weekday = DAYS[day.weekday()]
    missing = []
    for w in windows:
        if w.days is not None and weekday not in w.days:
            continue
        t, end = _hhmm(day, w.start), _hhmm(day, w.end)
        if day.date() == now.date() and slots:
            t = max(t, slots[0])
        while t < end:
            if t not in slots:
                missing.append(t)
            t += datetime.timedelta(minutes=minutes)
    return missing


@pytest.mark.flaky(reruns=0)
@allure.title("DPRF: profile, locations, hours, slot length, leaves and the slots patients see (read-only)")
def test_doctor_profile_and_slots(driver):
    home, tab = DoctorHomePage(driver), DoctorProfileTabPage(driver)
    hours, minutes = {}, {}

    with step("DPRF-01"):
        assert home.is_loaded(), "Doctor home ('Overview') did not load - is the test doctor logged in?"
        check_doctor(home.doctor_name())
        assert tab.open(), "Profile tab did not open"
        header = tab.header()
        _note(header, "profile header")
        check_doctor(header["name"])
        assert header["specialty"], f"No specialty under the name: {header}"
        assert header["verified"], "'Verified Profile' not shown"
        assert header["experience"].endswith("Yrs") and header["rating"], f"Experience/rating missing: {header}"
        rows, sections = tab.rows()
        _note(f"rows: {rows}\nsections: {sections}", "profile rows")
        missing = [r for r in MENU + ("Log Out",) if r not in rows] + [s for s in SECTIONS if s not in sections]
        assert not missing, f"Missing on the Profile tab: {missing}"

    with step("DPRF-02"):
        tab.open_row("View Profile")
        view = ViewProfilePage(driver)
        assert view.is_open(), "View Profile did not open"
        fields = view.fields()
        _note("\n".join(f"{k}: {v[0]} ({'EDITABLE' if v[1] else 'read-only'})" for k, v in fields.items()), "View Profile")
        assert not [f for f in PROFILE_FIELDS if f not in fields], f"Fields missing: {[f for f in PROFILE_FIELDS if f not in fields]}"
        editable = [k for k, (_v, can_edit) in fields.items() if can_edit]
        assert not editable, f"View Profile lets the doctor edit: {editable}"
        assert not [k for k in PROFILE_FIELDS if not fields[k][0]], "Empty field on View Profile"
        check_doctor(fields["Full Name"][0])
        assert fields["Specialization"][0] == header["specialty"], \
            f"Specialization '{fields['Specialization'][0]}' vs Profile tab '{header['specialty']}'"
        assert header["experience"].split()[0] == fields["Years of Experience"][0], \
            f"Experience '{fields['Years of Experience'][0]}' vs Profile tab '{header['experience']}'"
        view.go_back()
        _back_to_profile(driver, tab)

    with step("DPRF-03"):
        tab.open_row("Manage Locations")
        locations = ManageLocationsPage(driver)
        assert locations.is_open(), "Manage Locations did not open"
        cards = {c.name: c for c in locations.cards()}
        _note("\n".join(c.label() for c in cards.values()), "locations")
        assert set(cards) == set(DOCTOR_LOCATIONS), f"Locations shown {sorted(cards)}, expected {sorted(DOCTOR_LOCATIONS)}"
        for name, fee in DOCTOR_LOCATIONS.items():
            card = cards[name]
            assert card.fee == f"PKR {fee}", f"{name}: fee '{card.fee}', expected PKR {fee}"
            assert card.kind == ("Video" if name == VIDEO else "In-Person"), f"{name}: type '{card.kind}'"
            assert card.address, f"{name}: no address"

    with step("DPRF-04"):
        details = HospitalDetailsPage(driver)
        for name, fee in DOCTOR_LOCATIONS.items():
            locations.open_location(name)
            assert details.is_open(), f"Hospital Details did not open for {name}"
            info = details.read()
            windows = [s for s in info["slots"] if s.on]
            _note(f"{info.get('name')} | {info.get('address')} | fee {info.get('fee')}\n" +
                  "\n".join(s.label() for s in info["slots"]), f"Hospital Details - {name}")
            print(f"\n{name}: " + "; ".join(s.label() for s in info["slots"]))
            assert info.get("name") == name, f"Hospital Details shows '{info.get('name')}', expected {name}"
            assert info.get("fee") == fee, f"{name}: fee box '{info.get('fee')}', expected {fee}"
            assert windows, f"{name}: no consultation slot is switched ON"
            for w in windows:
                assert w.start and w.end and w.start < w.end, f"{name} {w.title}: bad hours {w.start}-{w.end}"
                assert w.days is None or w.days, f"{name} {w.title}: no day selected"
            hours[name] = windows
            details.go_back()
            assert locations.is_open(timeout=10), "Did not get back to Manage Locations"
        _back_to_profile(driver, tab)

    with step("DPRF-05"):
        tab.open_row("Scheduler Settings")
        scheduler = SchedulerSettingsPage(driver)
        assert scheduler.is_open(), "Scheduler Settings did not open"
        options = scheduler.options()
        _note(options, "location options")
        assert "All Locations" in options and set(DOCTOR_LOCATIONS) <= set(options), f"Options: {list(options)}"
        assert sum(options.values()) == 1, f"Not exactly one location option selected: {options}"
        for name in DOCTOR_LOCATIONS:
            scheduler.choose_location(name)                   # shows this location's rules; nothing is saved
            assert scheduler.options().get(name), f"Option '{name}' did not become selected"
            shown, shares = scheduler.slot_minutes()
            _note(f"selected: {shown} min; green share per chip: {shares}", f"slot length - {name}")
            minutes[name] = DOCTOR_SLOT_MINUTES[name]
            if Image is None:
                print("\nNOTE: Pillow is not installed, the selected slot length was not read (pip install pillow)")
            else:
                assert shown == DOCTOR_SLOT_MINUTES[name], \
                    f"{name}: Scheduler Settings shows {shown} min, expected {DOCTOR_SLOT_MINUTES[name]} min ({shares})"
        scheduler.go_back()
        _back_to_profile(driver, tab)

    with step("DPRF-06"):
        tab.open_row("Manage Leaves")
        leaves = ManageLeavesPage(driver)
        assert leaves.is_open(), "Manage Leaves did not open"
        leave_free = leaves.is_empty()
        _note("\n".join(leaves.texts()), "Manage Leaves")
        print(f"\nLEAVES: {'none' if leave_free else 'some - see the report'}")
        leaves.go_back()

    with step("DPRF-07"):
        now = _device_now(driver)
        days = [datetime.datetime.combine(now.date() + datetime.timedelta(days=i), datetime.time()) for i in (0, 1)]
        problems = []
        print(f"\nPHONE TIME: {now:%a %d %b %I:%M %p}")
        for name in DOCTOR_LOCATIONS:
            fee, chips, offered = offered_slots(driver, name, days)
            for day, slots in offered.items():
                listing = ", ".join(f"{t:%I:%M %p}" for t in slots) if slots else "none"
                _note(listing, f"{name} - {day:%a %d %b} slots")
                gone = _not_offered(day, slots or [], hours[name], minutes[name], now)
                gone_text = ", ".join(f"{t:%I:%M %p}" for t in gone) or "none"
                _note(gone_text, f"{name} - {day:%a %d %b} NOT offered (booked?)")
                print(f"{name} {day:%a %d %b}: {len(slots or [])} slots, first {listing[:8]}, last {listing[-8:]}; "
                      f"not offered: {gone_text if len(gone) <= 10 else f'{len(gone)} slots - see the report'}")
                problems += [f"{name}: {p}" for p in
                             _check_day(day, slots, hours[name], minutes[name], now, leave_free)]
            _note(f"card fee {fee}; date chips {chips}", f"{name} - Booking Summary")
        to_doctor_app(driver)
        assert not problems, "Slots patients see do not match the doctor's settings:\n" + "\n".join(problems)