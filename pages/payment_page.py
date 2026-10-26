import re

from appium.webdriver.common.appiumby import AppiumBy

from pages.base_page import BasePage, text_contains


class PaymentPage(BasePage):
    """The "Payment" screen: Total Payable Amount, Marham Wallet switch, payment methods, Pay button."""
    TITLE = text_contains("Total Payable Amount")
    WALLET_SWITCH = (AppiumBy.CLASS_NAME, "android.widget.Switch")
    BALANCE = text_contains("Balance: Rs.")
    WALLET_DEDUCTION = text_contains("Wallet Deduction")
    PAY_WITH_WALLET = text_contains("Pay with Wallet")
    # After paying: "Consultation Confirmed!" screen, then "View Receipt" -> "Transaction Receipt"
    CONFIRMED = text_contains("Consultation Confirmed")
    VIEW_RECEIPT = text_contains("View Receipt")
    RECEIPT_OK = text_contains("Payment Successful")
    BOOKING_ID = (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches("[0-9]{10,}")')

    def is_open(self, timeout=None):
        return self.is_visible(self.TITLE, timeout=timeout or self.TIMEOUT)

    def shows_amount(self, fee):
        """True if the big amount under Total Payable Amount is exactly 'Rs. <fee>'."""
        exact = (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("Rs. {fee}")')
        return self.is_visible(exact, timeout=5)

    def wallet_balance(self):
        """'Balance: Rs. 4,986' -> 4986"""
        digits = re.sub(r"[^0-9]", "", self.text_of(self.BALANCE))
        return int(digits) if digits else 0

    def turn_on_wallet(self):
        switch = self.find(self.WALLET_SWITCH)
        if switch.get_attribute("checked") != "true":
            switch.click()
        assert self.is_visible(self.WALLET_DEDUCTION, timeout=self.TIMEOUT), "Wallet switch did not turn on"

    def pay_with_wallet(self):
        self.tap(self.PAY_WITH_WALLET)

    def confirmed(self, timeout=40):
        return self.is_visible(self.CONFIRMED, timeout=timeout)

    def open_receipt(self):
        self.tap(self.VIEW_RECEIPT)
        return self.is_visible(self.RECEIPT_OK, timeout=self.TIMEOUT)

    def booking_id(self):
        return self.text_of(self.BOOKING_ID)