import allure
import pytest

from pages.home_page import HomePage
from pages.search_page import SearchPage
from test_data import NONSENSE_SEARCH, SPECIALTY
from utils.steps import step


@pytest.mark.search
@allure.title("SR-01: specialty search returns doctors")
def test_specialty_search(driver):
    with step("SR-01"):
        HomePage(driver).open_search()
        search = SearchPage(driver)
        search.search(SPECIALTY)
        assert search.result_count() >= 1, f"No doctors for {SPECIALTY}"


@pytest.mark.search
@allure.title("SR-02: nonsense search shows a no-results message")
def test_no_results_search(driver):
    with step("SR-02"):
        home = HomePage(driver)
        home.open_search()
        search = SearchPage(driver)
        search.search(NONSENSE_SEARCH)
        assert search.no_results_shown(), "No 'no results' message"
        assert not home.has_error()
