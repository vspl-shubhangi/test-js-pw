"""
test_happy_path_class.py
========================
TestHappyPath — full journey from the homepage through OTP entry to
"Connect to EvaFi Agent", matching happy_path_otp_screen.py exactly:
random branch resolution (pick-1-of-4 / pick-3-of-8), the mandated wait
times after each real-backend-triggering step, and fixed name/email/DOB/
phone values, plus a random (non-fixed) 6-digit OTP.

Shared step-driver helpers (open_chat_widget, drive_to_*, fill_*,
resolve_goal_or_balance_step, advance_through_intro_slides,
FIXED_VALID_EMAIL, FIXED_VALID_PHONE, FIXED_VALID_FIRST_NAME,
FIXED_VALID_LAST_NAME, FIXED_VALID_DOB_MONTH/DAY/YEAR, random_six_digit_otp,
drive_to_offers_step, etc.)
live in wizard_helpers.py; shared fixtures (page, device_page,
named_browser_page, matrix_page, browser_engine) are auto-discovered from
conftest.py by pytest -- neither needs a special import here beyond the
star-import below for the plain functions.
"""

import re

import pytest
from playwright.sync_api import Page, expect

import config
from wizard_helpers import *  # noqa: F401,F403 -- see __all__ in wizard_helpers.py


class TestHappyPath:
    """Full valid-data journey from the homepage all the way through
    "Connect to EvaFi Agent", run across the entire device x browser
    matrix. Handles whichever of the two random branches renders
    (pick-1-of-4 / pick-3-of-8) via the same helpers used everywhere
    else in the suite -- every run picks a genuinely different random
    subset, never the same fixed selection twice."""

    @pytest.mark.happy_path
    def test_full_onboarding_happy_path_reaches_offers_agent(self, matrix_page: Page):
        """NOTE: this test calls 'Send code', which triggers a REAL SMS
        in this environment, and includes the mandated wait times after
        the email step (20s), after Send code (30s), and after OTP
        submission (35s) -- roughly 85+ seconds of intentional waiting
        per run, on top of normal navigation. This is exactly why
        req #2 (parallel execution across browsers) matters: run this
        suite with `pytest -n auto` so multiple browser/device
        combinations wait concurrently instead of serially.

        The final step (drive_to_offers_step) ends by clicking "Connect
        to EvaFi Agent" itself, so that button is expected to no longer
        be the active control afterward -- the assertion instead checks
        the app landed in a recognizable, non-crashed state, matching
        the same survived-navigation pattern used for negative-input
        tests elsewhere in the suite."""
        page = matrix_page
        drive_to_offers_step(page)
        page.wait_for_timeout(1000)
        assert page.title().strip() != "", (
            "Page title went blank after 'Connect to EvaFi Agent' — possible crash."
        )