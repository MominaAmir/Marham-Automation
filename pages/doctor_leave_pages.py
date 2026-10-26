"""Doctor app (Marham Connect) - Profile > Manage Leaves: leave list, Add Leave form, Android date picker,
Delete Leave dialog. Locators from Appium Inspector + page source, 23 Oct 2026 (app 13.8, phone 720x1612).

Manage Leaves : title 'Manage Leaves', 'Upcoming Leaves', one card per location:
                '25 Oct 2026 - 25 Oct 2026', 'Video Consultation', 'Reason: Vacation', red bin icon (top right).
                Empty: 'No leaves scheduled'. Button: content-desc ', Add New Leave'.
Add Leave     : title 'Add Leave'. Location radios = clickable ViewGroup content-desc 'All Locations' /
                'Video Consultation' / '13-b Hospital' (selected one has an extra inner dot ViewGroup).
                Start Date / End Date = clickable ViewGroup content-desc ', Select date' (after a pick ', Oct 25, 2026').
                Reason = the only EditText. 'Save Leave' = content-desc 'Save Leave'.
                Toast: android.view.View content-desc ', Leave created successfully, '.
Date picker   : Android dialog. Day = View content-desc '25 October 2026' (past days enabled=false),
                android:id/next = Next month, android:id/date_picker_header_date 'Sun, 25 Oct', OK = android:id/button1.
Delete dialog : alert_title 'Delete Leave', 'Are you sure you want to delete this leave?',
                CANCEL android:id/button2, DELETE android:id/button1. Toast ', Leave deleted successfully, '.
                One card (one location) is deleted at a time.

Only tests/test_26_doctor_leave.py adds or deletes leaves, and it deletes only the leaves it added."""
import datetime
import re
import time
import xml.etree.ElementTree as ET

from selenium.common.exceptions import WebDriverException

from pages.base_page import BasePage
from pages.doctor_appointments_page import _tap_box, clean
from pages.doctor_home_page import exact
from pages.doctor_practice_pages import ManageLeavesPage, _box, _label, _scroll

ALL_LOCATIONS = "All Locations"
CREATED = "Leave created successfully"
DELETED = "Leave deleted successfully"
RANGE_RE = re.compile(r"^(\d{1,2} [A-Z][a-z]{2} \d{4}) - (\d{1,2} [A-Z][a-z]{2} \d{4})$")   # 25 Oct 2026 - 25 Oct 2026
SHOWN_RE = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}$")                                   # Oct 25, 2026
NOT_A_CARD = ("Manage Leaves", "Upcoming Leaves", "Add New Leave")


def _root(driver):
    return ET.fromstring(driver.page_source.encode("utf-8"))


def _strings(root):
    """Every text and content-desc on screen (icons removed): toasts are content-desc only."""
    found = []
    for n in root.iter():
        for value in (n.get("text"), n.get("content-desc")):
            value = clean(value).strip(" ,")
            if value and value not in found:
                found.append(value)
    return found


def tap_and_watch(driver, box, seconds=6):
    """Tap, then read the screen for a few seconds: returns the texts / descriptions that appeared."""
    try:
        before = set(_strings(_root(driver)))
    except WebDriverException:
        before = set()
    _tap_box(driver, box)
    new, end = [], time.time() + seconds
    while time.time() < end:
        time.sleep(0.7)
        try:
            new += [t for t in _strings(_root(driver)) if t not in before and t not in new]
        except WebDriverException:
            continue
    return new


def said(found, message):
    return any(message in t for t in found)


def shown_date(day):
    """How the Add Leave date buttons show a date: 'Oct 25, 2026'."""
    return f"{day:%b} {day.day}, {day.year}"


def card_range(day):
    """How a leave card shows a one-day leave: '25 Oct 2026 - 25 Oct 2026'."""
    one = f"{day.day} {day:%b %Y}"
    return f"{one} - {one}"


def _clickable(root, desc):
    return next((n for n in root.iter() if n.get("clickable") == "true" and clean(n.get("content-desc")) == desc), None)


# ---------------------------------------------------------------- Manage Leaves list
class Leave:
    def __init__(self, start, end, location, reason, bin_box):
        self.start, self.end, self.location, self.reason, self.bin_box = start, end, location, reason, bin_box

    def key(self):
        return (self.start, self.end, self.location, self.reason)

    def covers(self, day):
        day = day.date() if isinstance(day, datetime.datetime) else day
        return self.start <= day <= self.end

    def label(self):
        return f"{self.start:%d %b %Y} - {self.end:%d %b %Y} | {self.location} | Reason: {self.reason}"


def _text_nodes(node):
    return [clean(n.get("text")) for n in node.iter()
            if n.get("class") == "android.widget.TextView" and clean(n.get("text"))]


def leave_cards(root):
    """Leaves on the CURRENT screen. A card = the biggest box holding exactly one date range and one 'Reason'
    (and not the page title / header / Add button). Bin = the right-most clickable icon (no text) inside it."""
    parent = {k: p for p in root.iter() for k in p}

    def is_card(node):
        texts = _text_nodes(node)
        return (sum(bool(RANGE_RE.match(t)) for t in texts) == 1
                and sum(t.startswith("Reason") for t in texts) == 1
                and not any(t in NOT_A_CARD for t in texts))

    found = []
    for node in root.iter():
        if not is_card(node) or (node in parent and is_card(parent[node])):
            continue
        texts = _text_nodes(node)
        start, end = (datetime.datetime.strptime(v, "%d %b %Y").date() for v in RANGE_RE.match(
            next(t for t in texts if RANGE_RE.match(t))).groups())
        reason_at = next(i for i, t in enumerate(texts) if t.startswith("Reason"))
        reason = texts[reason_at].split(":", 1)[1].strip() if ":" in texts[reason_at] else ""
        if not reason and reason_at + 1 < len(texts):                 # 'Reason:' and 'Vacation' as two texts
            reason = texts[reason_at + 1]
        location = next((t for t in texts if not RANGE_RE.match(t) and not t.startswith("Reason") and t != reason), "")
        icons = [n for n in node.iter() if n is not node and n.get("clickable") == "true"
                 and not _text_nodes(n) and not clean(n.get("content-desc"))]
        bin_box = max((_box(n) for n in icons), key=lambda b: (b[2], -b[1]), default=None)
        found.append(Leave(start, end, location, reason, bin_box))
    return found


class LeavesPage(ManageLeavesPage):
    """Manage Leaves with the leave cards (ManageLeavesPage + reading, adding and deleting)."""

    def scroll_to_top(self):
        for _ in range(4):
            if not _scroll(self.driver, "up", 1.0):
                break

    def leaves(self, max_swipes=3):
        """Every leave in the list (scrolls down; the final scroll still moves the screen: read once more)."""
        self.scroll_to_top()
        found, last = {}, False
        for _ in range(max_swipes + 1):
            for leave in leave_cards(_root(self.driver)):
                found.setdefault(leave.key(), leave)
            if last:
                break
            last = not _scroll(self.driver, "down")
        return list(found.values())

    def _on_screen(self, wanted, max_swipes=3):
        """The first card on screen for which wanted(leave) is True (scrolls down to find it), or None."""
        self.scroll_to_top()
        last = False
        for _ in range(max_swipes + 1):
            card = next((c for c in leave_cards(_root(self.driver)) if wanted(c)), None)
            if card:
                return card
            if last:
                return None
            last = not _scroll(self.driver, "down")
        return None

    def open_add(self):
        node = next((n for n in _root(self.driver).iter()
                     if n.get("clickable") == "true" and _label(n.get("content-desc")) == "Add New Leave"), None)
        assert node is not None, "'Add New Leave' not on Manage Leaves"
        _tap_box(self.driver, _box(node))
        time.sleep(1)

    def delete(self, leave):
        """Bin of THIS leave -> 'Delete Leave' dialog -> DELETE. Returns the texts that appeared afterwards."""
        card = self._on_screen(lambda c: c.key() == leave.key())
        assert card, f"Leave not on Manage Leaves any more: {leave.label()}"
        assert card.bin_box, f"No bin icon found on the card {card.label()} (send the Manage Leaves page source)"
        _tap_box(self.driver, card.bin_box)
        dialog = DeleteLeaveDialog(self.driver)
        assert dialog.is_open(), f"Tapped the bin of {card.label()}, but no 'Delete Leave' dialog"
        return dialog.confirm()


class DeleteLeaveDialog(BasePage):
    TITLE = exact("Delete Leave")
    MESSAGE = "Are you sure you want to delete this leave?"

    def is_open(self, timeout=5):
        return self.is_visible(self.TITLE, timeout=timeout)

    def confirm(self):
        root = _root(self.driver)
        assert self.MESSAGE in _strings(root), f"'Delete Leave' dialog without '{self.MESSAGE}'"
        button = next((n for n in root.iter() if n.get("resource-id") == "android:id/button1"), None)
        assert button is not None and clean(button.get("text")).upper() == "DELETE", \
            f"'Delete Leave' dialog: right button is not DELETE ({None if button is None else button.get('text')})"
        return tap_and_watch(self.driver, _box(button))


# ---------------------------------------------------------------- Add Leave form
class AddLeavePage(BasePage):
    TITLE = exact("Add Leave")

    def is_open(self, timeout=None):
        return self.is_visible(self.TITLE, timeout=timeout or self.TIMEOUT)

    def options(self, root=None):
        """{location option: selected?}. An option = clickable ViewGroup whose desc is its own text and that has
        a radio circle ViewGroup; selected = the circle has the inner dot (2+ ViewGroups inside the option)."""
        root = root if root is not None else _root(self.driver)
        found = {}
        for node in root.iter():
            desc = clean(node.get("content-desc"))
            kids = list(node)
            texts = [clean(k.get("text")) for k in kids if k.get("class") == "android.widget.TextView"]
            circles = [k for k in node.iter() if k is not node and k.get("class") == "android.view.ViewGroup"]
            if node.get("clickable") == "true" and desc and texts == [desc] and circles:
                found[desc] = len(circles) >= 2
        return found

    def choose_location(self, name):
        node = _clickable(_root(self.driver), name)
        assert node is not None, f"Location option '{name}' not on Add Leave"
        _tap_box(self.driver, _box(node))
        time.sleep(1)
        assert self.options().get(name), f"Tapped '{name}' on Add Leave, but it is not selected: {self.options()}"

    def date_buttons(self, root=None):
        """[(box, shown text)] of Start Date and End Date, left to right ('Select date' or 'Oct 25, 2026')."""
        root = root if root is not None else _root(self.driver)
        buttons = []
        for n in root.iter():
            texts = [clean(k.get("text")) for k in n if clean(k.get("text"))]     # icon removed: one text left
            if n.get("clickable") == "true" and len(texts) == 1 and (texts[0] == "Select date" or SHOWN_RE.match(texts[0])):
                buttons.append((_box(n), texts[0]))
        return sorted(buttons, key=lambda b: b[0][0])

    def shown_dates(self):
        return [text for _box_, text in self.date_buttons()]

    def pick_date(self, which, day):
        """which 0 = Start Date, 1 = End Date: open the picker, choose the day, OK."""
        buttons = self.date_buttons()
        assert len(buttons) == 2, f"Expected Start Date and End Date buttons on Add Leave, found {buttons}"
        _tap_box(self.driver, buttons[which][0])
        DatePicker(self.driver).choose(day)

    def type_reason(self, text):
        boxes = self.driver.find_elements("class name", "android.widget.EditText")
        assert len(boxes) == 1, f"Expected one Reason box on Add Leave, found {len(boxes)}"
        boxes[0].click()
        boxes[0].clear()
        boxes[0].send_keys(text)
        try:
            self.driver.hide_keyboard()
        except WebDriverException:
            pass
        time.sleep(1)

    def reason(self):
        node = next((n for n in _root(self.driver).iter() if n.get("class") == "android.widget.EditText"), None)
        return clean(node.get("text")) if node is not None else ""

    def save(self):
        """Tap Save Leave; returns the texts that appeared ('Leave created successfully')."""
        node = _clickable(_root(self.driver), "Save Leave")
        assert node is not None, "'Save Leave' not on Add Leave"
        return tap_and_watch(self.driver, _box(node))


class DatePicker:
    """The Android date picker dialog opened by Start Date / End Date."""

    def __init__(self, driver):
        self.driver = driver

    def _wait(self, seconds=5):
        end = time.time() + seconds
        while time.time() < end:
            root = _root(self.driver)
            if any(n.get("resource-id") == "android:id/datePicker" for n in root.iter()):
                return root
            time.sleep(0.5)
        raise AssertionError("The date picker did not open")

    def choose(self, day, max_months=12):
        want = f"{day:%d %B %Y}"                                       # 25 October 2026 (content-desc of the day)
        root = self._wait()
        for _ in range(max_months + 1):
            cell = next((n for n in root.iter() if clean(n.get("content-desc")) == want), None)
            if cell is not None:
                break
            nxt = next((n for n in root.iter() if n.get("resource-id") == "android:id/next"), None)
            assert nxt is not None, f"'{want}' not in the date picker and no 'Next month' button"
            _tap_box(self.driver, _box(nxt))
            time.sleep(1)
            root = _root(self.driver)
        else:
            raise AssertionError(f"'{want}' not found in the date picker within {max_months} months")
        assert cell.get("enabled") == "true", f"'{want}' cannot be chosen in the date picker (disabled)"
        _tap_box(self.driver, _box(cell))
        time.sleep(0.7)
        root = _root(self.driver)
        header = next((clean(n.get("text")) for n in root.iter()
                       if n.get("resource-id") == "android:id/date_picker_header_date"), "")
        expected = f"{day:%a}, {day.day} {day:%b}"                     # Sun, 25 Oct
        assert header == expected, f"Date picker shows '{header}' after tapping {want}, expected '{expected}'"
        ok = next((n for n in root.iter() if n.get("resource-id") == "android:id/button1"), None)
        assert ok is not None and clean(ok.get("text")).upper() == "OK", "No OK button on the date picker"
        _tap_box(self.driver, _box(ok))
        time.sleep(1)