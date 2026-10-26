from test_data import APP_PACKAGE


def restart_app(driver):
    """Close the Marham app and open it again on the home screen."""
    driver.terminate_app(APP_PACKAGE)
    driver.activate_app(APP_PACKAGE)
