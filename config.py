"""
config.py
=========
Central configuration for the Evafi onboarding-wizard test suite.

Import as `import config` from any test module in tests/ (pytest adds the
rootdir to sys.path automatically when this file sits next to pytest.ini /
conftest.py, so no package __init__.py is required).

Values that differ per environment (local / staging / CI) are pulled from
environment variables when present, with sane local defaults as fallback.
Create a `.env` file (see .env.example) or export the vars in your shell /
CI job to override them.
"""
#9096392995

import os

from dotenv import load_dotenv

load_dotenv()  # loads a local .env file if present; no-op otherwise


# ─────────────────────────────────────────────────────────────────────────
# URLs
# ─────────────────────────────────────────────────────────────────────────

# Homepage that hosts the "Chat with Eva" launcher in the site navbar.
# FIX: defaulted to a placeholder production domain that doesn't match any
# of the captured flows — every Playwright Inspector recording so far was
# against the staging domain below. Override via EVAFI_LOGIN_URL for other
# environments.
LOGIN_URL = os.getenv("EVAFI_LOGIN_URL", "https://evafi.relintex.dev/")

# Base URL for the onboarding wizard itself (used as BASE_URL on test classes;
# informational / for future direct-navigation tests).
EVAFI_ONBOARDING_URL = os.getenv("EVAFI_ONBOARDING_URL", "https://evafi.relintex.dev/onboarding")


# ─────────────────────────────────────────────────────────────────────────
# Test data
# ─────────────────────────────────────────────────────────────────────────
# NOTE: first_name/last_name/email/phone are regenerated fresh per test run
# via the unique_* helpers in the test file itself where uniqueness matters.
# EVAFI_TEST_DATA below supplies the *static* values the generated flow
# currently fills in (e.g. captured during Playwright Inspector recording).
# Replace with your own fixture data as needed.

EVAFI_TEST_DATA = {
    "first_name": "Test",
    "last_name": "User",
    "email": "ankush@coreerp.com",
    # FIX: the previous placeholder "$10,000 - $25,000" does not match any
    # real button on the page and would fail to click. The Playwright
    # Inspector capture confirms the real button label is exactly "$30,000".
    "debt_amount": "$30,000",       # must exactly match the button label in the UI
    "dob_month": "01",
    "dob_day": "15",
    "dob_year": "1990",
    "phone_display": "(907) 575-2072",    # must match the masked input's expected format
}


# ─────────────────────────────────────────────────────────────────────────
# Negative-input payload library
# ─────────────────────────────────────────────────────────────────────────
# Reused across every text field in the wizard (first/last name, email,
# phone) by the TestRegression matrix in tests/test_evafi_onboarding.py.
# Centralized here so the SAME payloads are used for every field rather
# than scattered/rewritten per test.

EVAFI_INVALID_INPUTS = {
    "sql_injection":      "' OR '1'='1'; DROP TABLE users;--",
    "long_string_lower":  "a" * 300,
    "long_string_upper":  "A" * 300,
    "long_integer":       "2" * 25,
    "special_characters": "~!@#$%^&*()-{};'][\\",
    "unicode_text":       "Krithika_测试_😀_Ñoño_Ω_日本語",
}

# A real (accidental) malformed value observed during manual capture —
# kept as a dedicated boundary case for the phone field specifically,
# since it's an authentic near-miss rather than a synthetic payload.
EVAFI_PHONE_TOO_MANY_DIGITS = "(907) 575-2072"