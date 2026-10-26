import os

from appium.options.android import UiAutomator2Options

from test_data import APP_ACTIVITY, APP_PACKAGE


def android_options():
    o = UiAutomator2Options()
    o.device_name = "Android"
    udid = os.environ.get("ANDROID_UDID")          # only needed if more than one device is connected
    if udid:
        o.udid = udid
    o.app_package = APP_PACKAGE                    # the app already installed from the Play Store
    o.app_activity = APP_ACTIVITY
    o.no_reset = True                              # keep the login between runs
    o.new_command_timeout = 240
    o.disable_window_animation = True              # fewer timing flakes
    o.uiautomator2_server_launch_timeout = 90000   # first run on a new phone is slow
    o.adb_exec_timeout = 60000
    return o
