"""Small adb helpers for facts Appium does not give directly (app version, phone model)."""
import os
import re
import subprocess


def _shell(*args):
    cmd = ["adb"]
    udid = os.environ.get("ANDROID_UDID")
    if udid:
        cmd += ["-s", udid]
    cmd += ["shell", *args]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def app_version(package):
    m = re.search(r"versionName=(\S+)", _shell("dumpsys", "package", package))
    return m.group(1) if m else "unknown"


def device_info():
    return {
        "device_model": _shell("getprop", "ro.product.model").strip() or "unknown",
        "android_version": _shell("getprop", "ro.build.version.release").strip() or "unknown",
    }
