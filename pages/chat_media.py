"""Chat: send a FILE (picture) and a VOICE NOTE - same chat screen in both apps (see pages/chat_page.py).
Locators from Appium Inspector + page source, 23 Oct 2026 (phone 720x1612).

'+' (left of 'Enter message') -> menu, clickable ViewGroups content-desc 'Take a photo' / 'Take a video' /
'Photo library' / 'Files'. The tests only use FILES (never the photo library: it holds personal photos).
Files -> Android file picker (com.google.android.documentsui), 'Recent' list: each file = clickable
LinearLayout id item_root with TextView android:id/title = file name. Tapping it sends the file.
MIC (right of 'Enter message' while it is empty) -> panel: clickable ViewGroup content-desc '00:00' (timer),
TextView timer '00:00', 'Cancel' (content-desc), red RECORD button [328,1458][392,1522] (middle),
SEND [624,1457][690,1522] (right; enabled=false until something is recorded). Tap RECORD, wait, tap SEND.
Voice bubble: clickable ViewGroup content-desc '0:04' (length)."""
import datetime
import re
import time

from selenium.common.exceptions import WebDriverException

from pages.chat_page import TIME_RE, ChatPage, _box, _root
from pages.doctor_appointments_page import _tap_box, clean

TIMER_RE = re.compile(r"^(\d{2}):(\d{2})$")
PICKER_PACKAGE = "com.google.android.documentsui"
ATTACH_OPTIONS = ("Take a photo", "Take a video", "Photo library", "Files")


def _clickable_desc(root, desc):
    return next((n for n in root.iter() if n.get("clickable") == "true" and clean(n.get("content-desc")) == desc), None)


def _wait_root(driver, ok, seconds=10, what="screen"):
    end = time.time() + seconds
    while time.time() < end:
        try:
            root = _root(driver)
            if ok(root):
                return root
        except WebDriverException:
            pass
        time.sleep(0.7)
    raise AssertionError(f"{what} did not appear within {seconds} s")


class ChatMedia(ChatPage):
    # ---------- the two buttons beside the message box ----------
    def _side_buttons(self, root):
        """(left '+' box, right mic/send box) beside the EditText."""
        edit = _box(self._input(root))
        assert edit, "No message box on the chat screen"
        near = [_box(n) for n in root.iter() if n.get("clickable") == "true" and _box(n)
                and _box(n)[1] < edit[3] and _box(n)[3] > edit[1]]
        left = [b for b in near if b[2] <= edit[0] + 10]
        right = [b for b in near if b[0] >= edit[2] - 10]
        assert left and right, f"Buttons beside the message box not found (left {left}, right {right})"
        return max(left, key=lambda b: b[2]), min(right, key=lambda b: b[0])

    # ---------- file ----------
    def attach_menu(self):
        """Tap '+' and return the menu options shown."""
        plus, _mic = self._side_buttons(_root(self.driver))
        _tap_box(self.driver, plus)
        root = _wait_root(self.driver, lambda r: _clickable_desc(r, "Files") is not None, what="'+' menu")
        return [o for o in ATTACH_OPTIONS if _clickable_desc(root, o) is not None]

    def send_file(self, name, search=True):
        """'+' -> Files -> tap the file called `name` in the picker. Returns the menu options seen."""
        options = self.attach_menu()
        _tap_box(self.driver, _box(_clickable_desc(_root(self.driver), "Files")))
        root = _wait_root(self.driver, lambda r: any(n.get("package") == PICKER_PACKAGE for n in r.iter()),
                          seconds=15, what="File picker")
        item = self._picker_item(root, name)
        if item is None and search:                     # not in Recent: search for it by name
            button = next((n for n in root.iter() if clean(n.get("content-desc")) == "Search"
                           and n.get("clickable") == "true"), None)
            assert button is not None, f"'{name}' not in the file picker and no Search button"
            _tap_box(self.driver, _box(button))
            time.sleep(1)
            field = self.driver.find_elements("class name", "android.widget.EditText")
            assert field, "File picker search box not found"
            field[0].send_keys(name)
            self.driver.press_keycode(66)               # Enter
            time.sleep(2)
            item = self._picker_item(_root(self.driver), name)
        assert item is not None, f"Test file '{name}' not found in the file picker"
        _tap_box(self.driver, item)
        assert self.is_open(timeout=20), "Did not return to the chat after picking the file"
        return options

    @staticmethod
    def _picker_item(root, name):
        parent = {k: p for p in root.iter() for k in p}
        for n in root.iter():
            if n.get("resource-id") == "android:id/title" and clean(n.get("text")) == name:
                row = n
                while row is not None and not (row.get("resource-id") or "").endswith(":id/item_root"):
                    row = parent.get(row)
                return _box(row if row is not None else n)
        return None

    # ---------- voice note ----------
    @staticmethod
    def _panel(root):
        """(timer seconds, record box, send box, send enabled) of the voice panel, or None if it is not open."""
        panel = next((n for n in root.iter() if n.get("clickable") == "true"
                      and TIMER_RE.match(clean(n.get("content-desc")))), None)
        if panel is None:
            return None
        minutes, secs = TIMER_RE.match(clean(panel.get("content-desc"))).groups()
        pbox = _box(panel)
        buttons = [n for n in panel.iter() if n is not panel and n.get("class") == "android.view.ViewGroup"
                   and n.get("focusable") == "true" and not clean(n.get("content-desc")) and _box(n)[1] > pbox[1] + 100]
        record = min(buttons, key=lambda n: abs((_box(n)[0] + _box(n)[2]) / 2 - 360), default=None)
        send = max(buttons, key=lambda n: _box(n)[2], default=None)
        return (int(minutes) * 60 + int(secs), _box(record) if record is not None else None,
                _box(send) if send is not None else None, send is not None and send.get("enabled") == "true")

    def send_voice(self, seconds=4):
        """Mic -> RECORD -> wait -> SEND. Returns (problems before sending, recorded seconds shown)."""
        root = _root(self.driver)
        assert clean(self._input(root).get("text")) in ("", "Enter message"), \
            "Message box is not empty: the right button is SEND, not the mic"
        _plus, mic = self._side_buttons(root)
        _tap_box(self.driver, mic)
        root = _wait_root(self.driver, lambda r: self._panel(r) is not None, what="Voice note panel")
        timer, record, send, enabled = self._panel(root)
        problems = []
        if timer != 0:
            problems.append(f"timer shows {timer} s before recording")
        if enabled:
            problems.append("SEND is enabled before recording")
        assert record and send, "RECORD / SEND buttons not found in the voice panel"
        _tap_box(self.driver, record)
        time.sleep(seconds)
        timer, _record, send, enabled = self._panel(_root(self.driver))
        assert timer >= 2, f"Voice panel timer shows {timer} s after recording for {seconds} s"
        assert enabled, "SEND is still disabled after recording"
        _tap_box(self.driver, send)
        _wait_root(self.driver, lambda r: self._panel(r) is None, what="Chat after sending the voice note")
        return problems, timer

    def wait_new(self, kind, since, timeout=60):
        """Wait until the NEWEST message on screen is of this kind and was sent at/after `since` (phone time,
        whole minutes) - an older picture or voice note from an earlier run does not count.
        Returns (that message or the newest one of this kind seen, every message on screen)."""
        start = since.replace(second=0, microsecond=0)
        end, last = time.time() + timeout, (None, [])
        while True:
            try:
                every = self.messages()                     # ONE read
                wanted = [m for m in every if m.kind == kind]
                last = (wanted[-1] if wanted else None, every)
                newest = every[-1] if every else None
                if newest is not None and newest.kind == kind and TIME_RE.match(newest.time or ""):
                    shown = datetime.datetime.combine(since.date(),
                                                      datetime.datetime.strptime(newest.time, "%I:%M %p").time())
                    if start <= shown <= start + datetime.timedelta(minutes=3):
                        return newest, every
            except WebDriverException:
                pass
            if time.time() > end:
                return last
            self.scroll_to_bottom()
            time.sleep(2)

    def newest(self, kind=None, timeout=30):
        """Newest message (of this kind) on screen, waiting up to `timeout` for one."""
        end = time.time() + timeout
        while True:
            try:
                every = self.messages()                     # ONE read: the list may move a pixel between reads
                wanted = [m for m in every if kind is None or m.kind == kind]
                if wanted:
                    return wanted[-1], every
            except WebDriverException:
                pass
            if time.time() > end:
                return None, []
            self.scroll_to_bottom()
            time.sleep(2)


def make_test_image(path, label):
    """A small PNG with the label written on it (so it is easy to recognise in the chat)."""
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (480, 320), (230, 245, 240))
    draw = ImageDraw.Draw(image)
    draw.rectangle([10, 10, 470, 310], outline=(0, 150, 100), width=6)
    draw.text((40, 140), label, fill=(0, 0, 0))
    image.save(path)
    return path