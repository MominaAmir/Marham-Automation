"""Doctor app (Marham Connect) - Profile > PRACTICE MANAGEMENT screens:
Manage Locations, Hospital Details (opened with 'Edit Location'), Scheduler Settings, Manage Leaves.
Locators from Appium Inspector + page source, 22-23 Oct 2026 (app 13.8).

Reading never changes anything. CHANGING (only from tests/test_25_doctor_schedule.py, which always restores):
  Scheduler Settings: choose_minutes + save ('Scheduler settings updated', back to the Profile tab).
  Hospital Details:   toggle_day + save.
NEVER tapped by any test: Add Slot, the slot switch, the bin icon, time boxes, Add New Location, Add New Leave.

Selection shown only by colour (same page source): slot-length chip, day chips -> utils.screen_colour.
Selection shown in the page source: location option = its ViewGroup has an extra inner dot ViewGroup."""
import re
import time
import xml.etree.ElementTree as ET

from selenium.common.exceptions import WebDriverException

from pages.base_page import BasePage
from pages.doctor_appointments_page import _tap_box, clean
from pages.doctor_home_page import exact
from utils.screen_colour import selected_many, selected_one

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")          # chips show M T W T F S S in this order
MINUTES_RE = re.compile(r"^(\d+) min$")
HHMM_RE = re.compile(r"^(\d{2}):(\d{2})$")


def _box(node):
    numbers = re.findall(r"-?\d+", node.get("bounds") or "")
    return tuple(int(v) for v in numbers) if len(numbers) == 4 else None


def _root(driver):
    return ET.fromstring(driver.page_source.encode("utf-8"))


def _kids_texts(node):
    return [clean(k.get("text")) for k in node if k.get("class") == "android.widget.TextView" and clean(k.get("text"))]


def _label(desc):
    """', Edit Location' -> 'Edit Location'; '13-b Hospital' -> '13-b Hospital'."""
    parts = [p.strip() for p in clean(desc).split(",") if p.strip()]
    return parts[-1] if parts else ""


def _scroll(driver, direction, percent=0.7):
    size = driver.get_window_size()
    try:
        return driver.execute_script("mobile: scrollGesture", {
            "left": int(size["width"] * 0.1), "top": int(size["height"] * 0.3),
            "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.45),
            "direction": direction, "percent": percent})
    except WebDriverException:
        return False


def _texts(driver):
    return [clean(n.get("text")) for n in _root(driver).iter()
            if n.get("class") == "android.widget.TextView" and clean(n.get("text"))]


def tap_and_watch(driver, box, seconds=5):
    """Tap, then read the screen for a few seconds: returns the texts that appeared (toast / message)."""
    before = set(_texts(driver))
    _tap_box(driver, box)
    new, end = [], time.time() + seconds
    while time.time() < end:
        time.sleep(0.7)
        try:
            new += [t for t in _texts(driver) if t not in before and t not in new]
        except WebDriverException:
            continue
    return new


def _save_box(driver):
    node = next((n for n in _root(driver).iter()
                 if n.get("clickable") == "true" and clean(n.get("content-desc")) == "Save Changes"), None)
    assert node is not None, "'Save Changes' not on screen"
    return _box(node)


class LocationCard:
    def __init__(self, texts, edit_box):
        self.name = texts[0] if texts else ""
        self.kind = texts[1] if len(texts) > 1 else ""                       # Video / In-Person
        self.fee = next((t for t in texts if t.startswith("PKR ")), "")        # PKR 100
        self.address = next((t for t in texts[2:] if not t.startswith("PKR ")), "")
        self.edit_box = edit_box

    def label(self):
        return f"{self.name} | {self.kind} | {self.address} | {self.fee}"


class ManageLocationsPage(BasePage):
    TITLE = exact("Manage Locations")

    def is_open(self, timeout=None):
        return self.is_visible(self.TITLE, timeout=timeout or self.TIMEOUT)

    def cards(self, root=None):
        """Every location card on screen: a ViewGroup that has an 'Edit Location' button as its own child."""
        root = root if root is not None else _root(self.driver)
        found = []
        for parent in root.iter():
            edit = [k for k in parent if k.get("clickable") == "true" and _label(k.get("content-desc")) == "Edit Location"]
            if edit:
                found.append(LocationCard(_kids_texts(parent), _box(edit[0])))
        return found

    def open_location(self, name):
        """Tap 'Edit Location' on this location's card -> Hospital Details (read only from here on)."""
        card = next((c for c in self.cards() if c.name == name), None)
        assert card, f"Location '{name}' not on Manage Locations"
        _tap_box(self.driver, card.edit_box)
        time.sleep(1)


class ConsultationSlot:
    def __init__(self, title, on, day_boxes, times):
        self.title, self.on, self.day_boxes = title, on, day_boxes
        self.start = times[0] if times else ""
        self.end = times[1] if len(times) > 1 else ""
        self.days = None                                                       # filled from the screenshot

    def label(self):
        days = ", ".join(self.days) if self.days is not None else "days unknown (no Pillow)"
        return f"{self.title}: {'ON' if self.on else 'OFF'} | {days} | {self.start}-{self.end}"


class HospitalDetailsPage(BasePage):
    """'Hospital Details' (opened with Edit Location): location name, address, fee box, then
    'Editable Information' with Slot 1, Slot 2 ...: switch, Available Days M..S, Start / End."""
    TITLE = exact("Hospital Details")

    def is_open(self, timeout=None):
        return self.is_visible(self.TITLE, timeout=timeout or self.TIMEOUT)

    def read(self, max_swipes=4):
        """{'name', 'address', 'fee', 'slots': [ConsultationSlot]} - scrolls down for more slots."""
        info, slots = {}, {}
        last = False                                   # the final scroll still moves the screen: read once more
        for _ in range(max_swipes + 1):
            root = _root(self.driver)
            for node in root.iter():
                kids = list(node)
                texts = _kids_texts(node)
                if "Consultation Fee (PKR)" in texts:
                    box = next((k for k in node.iter() if k.get("class") == "android.widget.EditText"), None)
                    info.setdefault("fee", clean(box.get("text")) if box is not None else "")
                    info.setdefault("fee_editable", box is not None and box.get("enabled") == "true")
                title = next((t for t in texts if re.fullmatch(r"Slot \d+", t)), None)
                if title and title not in slots:
                    switch = next((k for k in kids if k.get("class") == "android.widget.Switch"), None)
                    days = [_box(k) for k in kids if k.get("clickable") == "true"
                            and clean(k.get("content-desc")) in ("M", "T", "W", "F", "S")]
                    times = [_label(k.get("content-desc")) for k in kids if k.get("clickable") == "true"
                             and HHMM_RE.match(_label(k.get("content-desc")))]
                    slot = ConsultationSlot(title, switch is not None and switch.get("checked") == "true", days, times)
                    if len(days) == 7:
                        picked = selected_many(self.driver, days)
                        slot.days = None if picked is None else [d for d, on in zip(DAYS, picked) if on]
                    slots[title] = slot
            if "name" not in info:
                header = [clean(n.get("text")) for n in root.iter()
                          if n.get("class") == "android.widget.TextView" and clean(n.get("text"))]
                if "Hospital Details" in header:
                    after = header[header.index("Hospital Details") + 1:]
                    after = [t for t in after if t != "Add Slot"]
                    info["name"] = after[0] if after else ""
                    info["address"] = after[2] if len(after) > 2 else ""
            if last:
                break
            last = not _scroll(self.driver, "down")
        info["slots"] = list(slots.values())
        return info

    def scroll_to_top(self):
        for _ in range(4):
            if not _scroll(self.driver, "up", 1.0):
                break

    def day_chips(self, title="Slot 1"):
        """(7 day-chip boxes M..S of this slot on the CURRENT screen, [selected?] from a screenshot or None)."""
        for node in _root(self.driver).iter():
            if title in _kids_texts(node):
                boxes = [_box(k) for k in node if k.get("clickable") == "true"
                         and clean(k.get("content-desc")) in ("M", "T", "W", "F", "S")]
                if len(boxes) == 7:
                    return boxes, selected_many(self.driver, boxes)
        raise AssertionError(f"Day chips of '{title}' not on screen")

    def toggle_day(self, weekday, title="Slot 1"):
        """Tap the chip of weekday (0 = Monday ... 6 = Sunday). Not saved until save()."""
        self.scroll_to_top()
        boxes, _ = self.day_chips(title)
        _tap_box(self.driver, boxes[weekday])
        time.sleep(1)

    def save(self):
        """Tap Save Changes; returns the texts that appeared afterwards."""
        self.scroll_to_top()
        return tap_and_watch(self.driver, _save_box(self.driver))

    def go_back(self):
        self.driver.back()
        time.sleep(1)


class SchedulerSettingsPage(BasePage):
    TITLE = exact("Scheduler Settings")

    def is_open(self, timeout=None):
        return self.is_visible(self.TITLE, timeout=timeout or self.TIMEOUT)

    def options(self, root=None):
        """{location option: selected?} - a selected option has an extra inner dot ViewGroup."""
        root = root if root is not None else _root(self.driver)
        found = {}
        for node in root.iter():
            texts = _kids_texts(node)
            if node.get("clickable") == "true" and texts and texts[0] == clean(node.get("content-desc")) \
                    and not MINUTES_RE.match(texts[0]) and texts[0] != "Save Changes":
                dots = [k for k in node if k.get("class") == "android.view.ViewGroup"]
                found[texts[0]] = len(dots) >= 2
        return found

    def choose_location(self, name):
        """Tap a location option (only shows its rules; nothing is saved)."""
        node = next((n for n in _root(self.driver).iter()
                     if n.get("clickable") == "true" and clean(n.get("content-desc")) == name), None)
        assert node is not None, f"Option '{name}' not on Scheduler Settings"
        _tap_box(self.driver, _box(node))
        time.sleep(1)

    def slot_minutes(self):
        """(selected minutes or None, {chip: green share}) - read from a screenshot."""
        chips = {int(MINUTES_RE.match(clean(n.get("content-desc"))).group(1)): _box(n)
                 for n in _root(self.driver).iter()
                 if n.get("clickable") == "true" and MINUTES_RE.match(clean(n.get("content-desc")))}
        return selected_one(self.driver, chips)

    def choose_minutes(self, minutes):
        """Tap the 'N min' chip (not saved until save())."""
        node = next((n for n in _root(self.driver).iter()
                     if n.get("clickable") == "true" and clean(n.get("content-desc")) == f"{minutes} min"), None)
        assert node is not None, f"Chip '{minutes} min' not on Scheduler Settings"
        _tap_box(self.driver, _box(node))
        time.sleep(1)

    def save(self):
        """Tap Save Changes; returns the texts that appeared ('Scheduler settings updated')."""
        return tap_and_watch(self.driver, _save_box(self.driver))

    def go_back(self):
        self.driver.back()
        time.sleep(1)


class ManageLeavesPage(BasePage):
    TITLE = exact("Manage Leaves")
    EMPTY = "No leaves scheduled"

    def is_open(self, timeout=None):
        return self.is_visible(self.TITLE, timeout=timeout or self.TIMEOUT)

    def texts(self):
        return [clean(n.get("text")) for n in _root(self.driver).iter()
                if n.get("class") == "android.widget.TextView" and clean(n.get("text"))]

    def is_empty(self):
        return self.EMPTY in self.texts()

    def go_back(self):
        self.driver.back()
        time.sleep(1)