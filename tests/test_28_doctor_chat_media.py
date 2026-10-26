"""Chat FILE + VOICE NOTE, checked in BOTH apps.                     pytest -m doctor_chat_media -s
1. A test picture 'AT_chat_<time>.png' (text written on it) is put in the phone's Download folder.
2. Doctor app chat: '+' -> Files -> that picture -> it is the newest message, on the RIGHT, time correct.
3. Patient app chat: the picture arrives on the LEFT (received).
4. Patient app: mic -> RECORD -> about 4 s -> SEND -> newest message is a voice note on the RIGHT.
5. Doctor app chat: the voice note arrives on the LEFT with the same length.
6. Clean-up (always): the test picture is removed from the phone's Download folder.
Never uses 'Photo library' or the camera (no personal photos are ever sent). Chat messages cannot be deleted:
one picture and one short voice note are sent per run."""
import contextlib
import datetime
import os
import tempfile

import allure
import pytest

from pages.chat_media import ChatMedia, make_test_image
from pages.chat_page import time_matches
from utils import adb
from utils.chat_open import doctor_chat as _doctor_chat, patient_chat as _patient_chat
from utils.steps import step

pytestmark = [pytest.mark.doctor_app, pytest.mark.doctor_chat_media]

PHONE_FOLDER = "/sdcard/Download"
VOICE_SECONDS = 4


def _note(text, name):
    allure.attach(str(text), name=name, attachment_type=allure.attachment_type.TEXT)


def _now(driver):
    return datetime.datetime.strptime(driver.get_device_time("YYYY-MM-DD HH:mm:ss"), "%Y-%m-%d %H:%M:%S")


@contextlib.contextmanager
def _soft(failures, label):
    try:
        yield
    except AssertionError as exc:
        failures.append(f"{label}: {exc}")


def _show(shown, name):
    _note("\n".join(m.label() for m in shown) or "no messages", name)


def _check(message, shown, kind, side, now, who, what):
    _show(shown, f"{who} chat")
    assert message is not None, f"{who} chat: no {what} found. Last messages: " + \
                                "; ".join(m.label() for m in shown[-4:])
    assert shown[-1] is message, f"{who} chat: the {what} is not the newest message (newest: {shown[-1].label()})"
    assert message.side == side, f"{who} chat: the {what} is on the {message.side} side, expected {side}"
    assert time_matches(message.time, now), (f"{who} chat: newest {what} has time '{message.time}', phone time "
                                             f"{now:%I:%M %p} - the new one did not appear within the wait (old one from an earlier run?)")


def _media_chat(open_chat, driver):
    open_chat(driver)
    return ChatMedia(driver)


@pytest.mark.flaky(reruns=0)
@allure.title("DMED: doctor sends a picture, patient sends a voice note - each reaches the other app")
def test_chat_file_and_voice(driver):
    stamp = _now(driver)
    name = f"AT_chat_{stamp:%H%M%S}.png"
    remote = f"{PHONE_FOLDER}/{name}"
    print(f"\nPHONE TIME {stamp:%a %d %b %I:%M %p} | doctor sends picture '{name}' | patient sends a {VOICE_SECONDS} s voice note")
    failures, pushed = [], False
    try:
        with step("DMED-01"):
            local = make_test_image(os.path.join(tempfile.gettempdir(), name), f"Automation test {stamp:%d %b %H:%M:%S}")
            driver.push_file(remote, source_path=local)
            pushed = True
            adb._shell("am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{remote}")
            assert name in adb._shell("ls", PHONE_FOLDER), f"Test picture '{name}' is not in {PHONE_FOLDER} on the phone"

        with step("DMED-02"):
            chat = _media_chat(_doctor_chat, driver)
            now = _now(driver)
            options = chat.send_file(name)
            _note(options, "'+' menu options")
            picture, shown = chat.wait_new("image", now)              # upload can take a few seconds
            _check(picture, shown, "image", "sent", now, "Doctor", "picture")

        with step("DMED-03"):
            chat = _media_chat(_patient_chat, driver)
            picture, shown = chat.wait_new("image", now, timeout=30)
            if picture is None or picture.side != "received" or not time_matches(picture.time, now):
                chat = _media_chat(_patient_chat, driver)          # reopen once (refresh)
                picture, shown = chat.wait_new("image", now, timeout=30)
            _check(picture, shown, "image", "received", now, "Patient", "picture from the doctor")

        with step("DMED-04"):
            now = _now(driver)
            problems, recorded = chat.send_voice(VOICE_SECONDS)
            with _soft(failures, "DMED-04 voice panel"):
                assert not problems, "Voice panel before recording: " + "; ".join(problems)
            voice, shown = chat.wait_new("voice", now)
            _check(voice, shown, "voice", "sent", now, "Patient", "voice note")
            assert abs(voice.seconds() - recorded) <= 1, \
                f"Patient: voice note is {voice.text} long, the panel showed {recorded} s when SEND was tapped"

        with step("DMED-05"):
            chat = _media_chat(_doctor_chat, driver)
            heard, shown = chat.wait_new("voice", now, timeout=30)
            if heard is None or heard.side != "received" or not time_matches(heard.time, now):
                chat = _media_chat(_doctor_chat, driver)
                heard, shown = chat.wait_new("voice", now, timeout=30)
            _check(heard, shown, "voice", "received", now, "Doctor", "voice note from the patient")
            assert heard.text == voice.text, f"Doctor: voice note is {heard.text} long, the patient sent {voice.text}"
            own = [m for m in shown if m.kind == "image" and m.side == "sent"]
            with _soft(failures, "DMED-05 picture"):
                assert own, "Doctor: own picture is no longer shown on the right after reopening the chat"
    finally:
        if pushed:
            with step("DMED-06"):
                adb._shell("rm", "-f", remote)
                assert name not in adb._shell("ls", PHONE_FOLDER), f"Delete '{name}' from the phone's Download folder by hand"
    assert not failures, "Chat file / voice problems:\n" + "\n".join(failures)