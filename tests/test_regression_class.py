"""
test_regression_class.py
========================
TestRegression — split out of the original monolithic test file so each test
class lives in its own file under tests/, matching the project's folder
structure. Shared step-driver helpers (open_chat_widget, drive_to_*,
fill_*, resolve_goal_or_balance_step, advance_through_intro_slides, DATA,
etc.) live in wizard_helpers.py; shared fixtures (page, device_page,
named_browser_page, matrix_page, browser_engine) are auto-discovered from
conftest.py by pytest -- neither needs a special import here beyond the
star-import below for the plain functions.
"""

import re

import pytest
from playwright.sync_api import Page, expect

import config
from wizard_helpers import *  # noqa: F401,F403 -- see __all__ in wizard_helpers.py


class TestRegression:

    # ── First legal name ──────────────────────────────────────────────
    @pytest.mark.regression
    @pytest.mark.parametrize("case_name,payload", INVALID_CASES, ids=INVALID_IDS)
    def test_first_name_field_survives_invalid_input(self, page: Page, case_name, payload):
        drive_to_name_step(page)
        page.get_by_role("textbox").first.fill(payload)
        page.get_by_role("textbox").nth(1).fill(FIXED_VALID_LAST_NAME)
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    # ── Last legal name ───────────────────────────────────────────────
    @pytest.mark.regression
    @pytest.mark.parametrize("case_name,payload", INVALID_CASES, ids=INVALID_IDS)
    def test_last_name_field_survives_invalid_input(self, page: Page, case_name, payload):
        drive_to_name_step(page)
        page.get_by_role("textbox").first.fill(FIXED_VALID_FIRST_NAME)
        page.get_by_role("textbox").nth(1).fill(payload)
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    # ── Email ─────────────────────────────────────────────────────────
    @pytest.mark.regression
    @pytest.mark.parametrize("case_name,payload", INVALID_CASES, ids=INVALID_IDS)
    def test_email_field_survives_invalid_input(self, page: Page, case_name, payload):
        drive_to_email_step(page)
        page.get_by_role("textbox").fill(payload)
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    # ── Phone number ──────────────────────────────────────────────────
    # NOTE: we deliberately do NOT click "Send code" for these payloads —
    # that button triggers a REAL SMS, and none of these payloads are
    # plausible phone numbers. We only verify the masked field itself
    # stays stable (accepts/rejects/truncates the payload without
    # crashing the page), not the send-code round trip.
    @pytest.mark.regression
    @pytest.mark.parametrize("case_name,payload", INVALID_CASES, ids=INVALID_IDS)
    def test_phone_field_survives_invalid_input(self, page: Page, case_name, payload):
        drive_to_phone_step(page)
        phone_field = page.get_by_role("textbox", name="(000) 000-")
        phone_field.fill(payload)
        page.wait_for_timeout(500)
        expect(phone_field).to_be_visible()
        assert page.title().strip() != ""

    @pytest.mark.regression
    def test_phone_field_rejects_too_many_digits(self, page: Page):
        """Dedicated boundary case: a real malformed value observed during
        manual capture (11 digits instead of 10) should not be silently
        accepted as a valid, sendable phone number."""
        drive_to_phone_step(page)
        phone_field = page.get_by_role("textbox", name="(000) 000-")
        phone_field.fill(config.EVAFI_PHONE_TOO_MANY_DIGITS)
        send_btn = page.get_by_role("button", name="Send code")
        if send_btn.is_enabled():
            value = phone_field.input_value()
            assert value != config.EVAFI_PHONE_TOO_MANY_DIGITS or len(value) <= len(FIXED_VALID_PHONE), (
                "Phone field accepted an 11-digit value verbatim with no "
                "masking/truncation/validation."
            )


# ═════════════════════════════════════════════════════════════════════════
# 6. TestCrossBrowserMatrix — chrome, chromium, firefox, brave, msedge, all
#    in ONE pytest run via the named_browser_page fixture above. This is
#    additive to TestCrossBrowser (which relies on re-running the file
#    with different --browser CLI flags) — it doesn't replace it.
# ═════════════════════════════════════════════════════════════════════════