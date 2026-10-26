"""Doctor app settings. The test doctor's phone number and OTP are NEVER saved here:
the login test asks for them while it runs."""

# --- App (open the doctor app, then: adb shell dumpsys window | findstr mCurrentFocus) ---
DOCTOR_APP_PACKAGE = "com.ts.marham_connect"
DOCTOR_APP_ACTIVITY = "com.ts.marham_connect.MainActivity"
DOCTOR_EXPECTED_APP_VERSION = "13.8"            # Android's versionName (the app screen shows "13.8.0")
# --- Test doctor logged in to the doctor app (exactly as on Home, capitals don't matter) ---
DOCTOR_APP_NAME = "Dr. Momina Testing"

# --- Login test ---
WRONG_OTP = "0000"                              # must be wrong; same number of digits as the real OTP

WRONG_PASSWORD = "Wrong#Pass123"                # login test: must NOT be the real password
# --- Patients on the test doctor's appointments that are OUR test accounts (exactly as on the cards) ---
# --- Flow 3: accept (the same doctor account is called "Dr. Momina Testing" in the patient app) ---
PATIENT_APP_DOCTOR_NAME = "Dr. Momina Testing"
DOCTOR_HOSPITAL = "13-b Hospital"
DOCTOR_CLINIC_FEE = "100"                           # Manage Locations: 13-b Hospital PKR 100
ACCEPT_MESSAGE = "Appointment confirmed successfully"

# --- Flow 3: accept (the same doctor account is called "Dr. Momina Testing" in the patient app) ---
PATIENT_APP_DOCTOR_NAME = "Dr. Momina Testing"
VIDEO = "Video Consultation"
DOCTOR_LOCATIONS = {                                # Manage Locations in the doctor app: name -> fee (PKR)
    "13-b Hospital": "100",
    VIDEO: "2",
}
ACCEPT_MESSAGE = "Appointment confirmed successfully"
DOCTOR_APP_NAME = "Dr. Momina Testing"
DOCTOR_SLOT_MINUTES = {"Video Consultation": 10, "13-b Hospital": 5}   # Scheduler Settings