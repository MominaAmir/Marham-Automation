"""Everything that changes between environments lives here. Fill in every REPLACE value."""

# --- App (Step 3.4: find these with adb) ---
APP_PACKAGE = "controllers.marham.marhammed"        # e.g. com.something.marham
APP_ACTIVITY = ".MainActivity"      # e.g. .MainActivity
EXPECTED_APP_VERSION = "29.9"                          # e.g. "5.2.1". Leave "" to only record the version.

# --- Test patient (Step 6). The OTP is NOT stored here: set env var MARHAM_TEST_OTP if you have a fixed OTP. ---
TEST_PHONE = "03116771305"
TEST_PATIENT_NAME = "Momina Amir"
FAMILY_MEMBERS = ["Unaiza Nasir", "Tooba"]       # exactly as shown under "Appointment For"
# --- Test doctor and clinic (Step 6) ---
ALLOW_OC_PAYMENT = True                           # True = book + pay Rs. 3 from Marham Wallet (real!)
ALLOW_PC_BOOKING = True                           # set True only after the Step 6 sign-off
DOCTOR_NAME = "Prof. Dr. Ehsan Bhatti (Testing Account)"
SPECIALTY = "Dermatologist"                        # used by SR-01
HOSPITAL = "13-b Hospital"
HOSPITAL_ADDRESS = "Garden Town Lahore"
OC_FEE = "3"
PC_FEE = "20"
# --- Texts the app shows (copy exactly from the app) ---
CANCELLED_STATUS = "Cancelled"
NONSENSE_SEARCH = "zzqxvq"                         # SR-02: must return no results
CANCEL_REASON = "Doctor was not available at the time of consultation."   # RF-03: reason the test picks

# --- Friends & Family (test_08_family). Test members are called "Autotest" + 4 letters and deleted after each test. ---
FAMILY_TEST_PREFIX = "Autotest"                  # ONLY members whose name starts with "Autotest " are ever deleted
FAMILY_RELATIONS_PROFILE = ["Father", "Mother", "Brother", "Sister", "Husband", "Wife", "Son", "Daughter"]
FAMILY_RELATIONS_BOOKING = ["Father", "Mother", "Husband", "Wife", "Son", "Daughter"]   # Booking Summary sheet
FAMILY_RELATION = "Son"                          # FAM-05: member added from Profile
FAMILY_GENDER = "Male"                           # gender the card shows for FAMILY_RELATION (Profile form has no gender)
FAMILY_PHONE = "03116771305"                     # the test account's own number - never use someone else's
FAMILY_SHORT_PHONE = "0300123"                   # FAM-04: fewer than 11 digits -> must give an error
FAMILY_BOOKING_RELATION = "Daughter"             # FAM-12: member added from Booking Summary
FAMILY_BOOKING_GENDER = "Female"
FAMILY_DEFAULT_PHONE_SHOWN = "+923116771305"     # card shows the account's number when the phone is left empty
FAMILY_FILL_ALERT = "Please fill name and relationship"   # FAM-11: alert for an empty form on Booking Summary