"""Doctor app (Marham Connect) - Appointments tab (Upcoming / Completed / Others) and Appointment Details.
READ-ONLY helpers: nothing here taps Start Session, Chat, Showed Up, Not Showed Up or any other action.
Locators from Appium Inspector + page source, 21 Oct 2026 (app 13.8).

Speed: the screen is read with ONE page-source call (then searched on the laptop) instead of one
Appium call per card, per button and per text - over Wi-Fi each call costs time."""
import re
import time
import unicodedata
import xml.etree.ElementTree as ET

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import WebDriverException

from pages.base_page import BasePage
from pages.doctor_home_page import DoctorHomePage, exact

UI = AppiumBy.ANDROID_UIAUTOMATOR
# Each card is a ViewGroup whose content-desc holds the card text, e.g.
# "SCHEDULED, UP NEXT, MA, Momina Amir, , Date, Oct 21, 2026, , Time, 10:10 AM, , Location, Video Consultation"
CARD = (UI, 'new UiSelector().className("android.view.ViewGroup").descriptionContains(", Date, ")')
DATE_RE = re.compile(r"Date, ([A-Z][a-z]{2} \d{1,2}, \d{4})")
TIME_RE = re.compile(r"Time, (\d{1,2}:\d{2} [AP]M)")
LOCATION_RE = re.compile(r"Location, ([^,]+)")


def desc_starts(text):
    return (UI, f'new UiSelector().descriptionStartsWith("{text}")')


def clean(text):
    """Remove the app's icon characters (private-use glyphs that look like empty boxes) and extra spaces."""
    return " ".join("".join(ch for ch in (text or "") if unicodedata.category(ch) != "Co").split())


def label_of(desc):
    """Buttons have content-desc '<icon>, <label>' -> '<label>' (', View Detail' -> 'View Detail')."""
    return clean(desc).split(",")[-1].strip()


def screen_nodes(driver):
    """Everything on screen from ONE page-source call: [{class, text, desc, clickable, checked, box}]."""
    root = ET.fromstring(driver.page_source.encode("utf-8"))
    nodes = []
    for n in root.iter():
        numbers = re.findall(r"-?\d+", n.get("bounds") or "")
        if len(numbers) != 4:
            continue
        nodes.append({"class": n.get("class") or "", "text": clean(n.get("text")),
                      "desc": clean(n.get("content-desc")), "clickable": n.get("clickable") == "true",
                      "checked": n.get("checked") == "true", "box": tuple(int(v) for v in numbers)})
    return nodes


def _inside(inner, outer):
    x, y = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
    return outer[0] <= x <= outer[2] and outer[1] <= y <= outer[3]


def _buttons(nodes):
    """(label, box) of every clickable ViewGroup with a content-desc."""
    return [(label_of(n["desc"]), n["box"]) for n in nodes
            if n["clickable"] and n["class"] == "android.view.ViewGroup" and label_of(n["desc"])]


def _tap_box(driver, box):
    driver.execute_script("mobile: clickGesture", {"x": (box[0] + box[2]) // 2, "y": (box[1] + box[3]) // 2})


BUTTON_LABELS = ("Start Session", "View Detail", "Chat", "Showed Up", "Not Showed Up")


class Card:
    """One appointment card, read from its content-desc. The parts are found by their labels
    ('Date', 'Time', 'Location'), so hidden icon characters or empty parts do not matter."""

    def __init__(self, desc, buttons=()):
        desc = clean(desc)
        self.desc = desc
        parts = [p.strip() for p in desc.split(",")]
        self.status = parts[0] if parts else ""                         # SCHEDULED ...
        names = [p for p in (parts[:parts.index("Date")] if "Date" in parts else []) if p]
        self.patient = names[-1] if len(names) > 1 else ""            # last text before 'Date': Momina Amir
        found = DATE_RE.search(desc)
        self.date = found.group(1) if found else ""                    # Oct 21, 2026
        found = TIME_RE.search(desc)
        self.time = found.group(1) if found else ""                    # 10:10 AM
        found = LOCATION_RE.search(desc)
        self.location = found.group(1).strip() if found else ""        # Video Consultation / 13-b Hospital
        # Buttons seen on screen, plus the ones the app lists in the card text (it does that when the
        # buttons are below the visible part of the screen).
        after = parts[parts.index("Location") + 2:] if "Location" in parts else []
        self.buttons = list(buttons) + [p for p in after if p in BUTTON_LABELS and p not in buttons]

    @property
    def key(self):
        return self.date, self.time, self.patient, self.location

    @property
    def is_video(self):
        return self.location == "Video Consultation"

    def label(self):
        return f"{self.status} | {self.patient} | {self.date} {self.time} | {self.location} | buttons: {self.buttons}"


class DoctorAppointmentsPage(BasePage):
    TITLE = exact("Appointments")
    DATE_RANGE = (AppiumBy.ACCESSIBILITY_ID, "Choose date range")
    TABS = ("Upcoming", "Completed", "Others")
    EMPTY = exact("No appointments found")

    def open(self):
        DoctorHomePage(self.driver).open_tab("Appointments")
        return self.is_visible(self.TITLE, timeout=self.TIMEOUT) and self.wait_loaded()

    def wait_loaded(self, timeout=15):
        """Until a card or 'No appointments found' is shown."""
        end = time.time() + timeout
        while time.time() < end:
            if self.driver.find_elements(*CARD) or self.driver.find_elements(*self.EMPTY):
                return True
            time.sleep(0.5)
        return False

    # ---------- tabs and date range ----------
    def tab(self, name):
        found = self.driver.find_elements(*desc_starts(name))
        return found[0] if found else None

    def tab_count(self, name):
        """'Upcoming, 5' -> 5; None if the tab shows no number."""
        el = self.tab(name)
        found = re.search(r",\s*(\d+)\s*$", (el.get_attribute("content-desc") or "") if el else "")
        return int(found.group(1)) if found else None

    def open_tab(self, name):
        el = self.tab(name)
        assert el is not None, f"Tab '{name}' not found"
        el.click()
        time.sleep(1)
        self.wait_loaded()

    def date_range_text(self):
        """Text of the 'Choose date range' box, e.g. 'Showing Today – Wed, 28 Oct'."""
        nodes = screen_nodes(self.driver)
        box = next((n["box"] for n in nodes if n["desc"] == "Choose date range"), None)
        assert box, "'Choose date range' box not found"
        return " ".join(n["text"] for n in nodes if n["text"] and n["class"].endswith("TextView") and _inside(n["box"], box))

    # ---------- scrolling ----------
    def _scroll(self, direction, percent=0.6):
        size = self.driver.get_window_size()
        try:
            return self.driver.execute_script("mobile: scrollGesture", {
                "left": int(size["width"] * 0.1), "top": int(size["height"] * 0.35),
                "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.45),
                "direction": direction, "percent": percent})
        except WebDriverException:
            return False

    def scroll_to_top(self):
        for _ in range(10):
            if not self._scroll("up", 1.0):
                break

    # ---------- cards ----------
    def cards_on_screen(self, nodes=None):
        """[(Card, card box)] on screen now, each with the buttons that sit inside it."""
        nodes = nodes if nodes is not None else screen_nodes(self.driver)
        buttons = _buttons(nodes)
        return [(Card(n["desc"], [label for label, box in buttons if _inside(box, n["box"])]), n["box"])
                for n in nodes if n["class"] == "android.view.ViewGroup" and ", Date, " in n["desc"]]

    def cards(self, max_swipes=10):
        """Every card of the open tab (scrolls down, then back to the top). Buttons seen on screen are kept."""
        found = {}
        for _ in range(max_swipes):
            for card, _box in self.cards_on_screen():
                old = found.setdefault(card.key, card)
                old.buttons += [b for b in card.buttons if b not in old.buttons]
            if not self._scroll("down"):
                break
        self.scroll_to_top()
        return list(found.values())

    def open_details(self, card, max_swipes=12):
        """Tap 'View Detail' inside this card (the card itself does not open anything)."""
        self.scroll_to_top()
        for _ in range(max_swipes):
            nodes = screen_nodes(self.driver)
            for shown, box in self.cards_on_screen(nodes):
                if shown.key == card.key:
                    for label, button_box in _buttons(nodes):
                        if label == "View Detail" and _inside(button_box, box):
                            _tap_box(self.driver, button_box)
                            return
            if not self._scroll("down", 0.3):                 # button may be below the screen: move a little
                break
        raise AssertionError(f"'View Detail' not found for card {card.label()}")


class AppointmentDetailsPage(BasePage):
    TITLE = exact("Appointment Details")
    PAYMENT = "Payment Details"

    def is_open(self, timeout=None):
        return self.is_visible(self.TITLE, timeout=timeout or self.TIMEOUT)

    def texts(self, nodes=None):
        nodes = nodes if nodes is not None else screen_nodes(self.driver)
        return [n["text"] for n in nodes if n["text"] and n["class"] == "android.widget.TextView"]

    def buttons(self, nodes=None):
        """Labels of the buttons on screen: Start Session, Chat with Patient, Mark Showed Up ..."""
        nodes = nodes if nodes is not None else screen_nodes(self.driver)
        return [label for label, _box in _buttons(nodes)]

    def chat_access_on(self, nodes=None):
        """True / False for the Patient Chat Access switch, None if it is not on screen."""
        nodes = nodes if nodes is not None else screen_nodes(self.driver)
        switch = next((n for n in nodes if n["class"] == "android.widget.Switch"), None)
        return switch["checked"] if switch else None

    def payment_texts(self, max_swipes=5):
        """Scroll down and return the texts below 'Payment Details' (fee, status, total ...)."""
        seen = []
        size = self.driver.get_window_size()
        for _ in range(max_swipes):
            seen += [t for t in self.texts() if t not in seen]
            try:
                more = self.driver.execute_script("mobile: scrollGesture", {
                    "left": int(size["width"] * 0.1), "top": int(size["height"] * 0.3),
                    "width": int(size["width"] * 0.8), "height": int(size["height"] * 0.5),
                    "direction": "down", "percent": 0.8})
            except WebDriverException:
                more = False
            if not more:
                seen += [t for t in self.texts() if t not in seen]
                break
        return seen[seen.index(self.PAYMENT) + 1:] if self.PAYMENT in seen else []

    def go_back(self):
        self.driver.back()