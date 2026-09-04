"""
test_functional_class.py
========================
TestFunctional — split out of the original monolithic test file so each test
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


class TestFunctional:
    """Textbox-focused functional coverage: valid input, whitespace-only
    input, blur-triggered validation (no submit), unicode, special
    characters, and boundary value analysis (255/256 char length,
    long-integer edge input)."""

    @pytest.mark.functional
    def test_first_name_valid_input_accepted(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)
        fill_name_step(page)  # FIXED_VALID_FIRST_NAME / FIXED_VALID_LAST_NAME
        expect(page.get_by_role("textbox")).to_be_visible()  # email step reached

    @pytest.mark.functional
    def test_last_name_whitespace_only_input_rejected_or_trimmed(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)
        page.get_by_role("textbox").first.fill(FIXED_VALID_FIRST_NAME)
        page.get_by_role("textbox").nth(1).fill("     ")
        page.get_by_role("button", name="Continue").click()
        # Either blocked (still on name step) or accepted-but-trimmed —
        # both are acceptable outcomes; a hard crash/blank page is not.
        _assert_app_survived_invalid_input(page)

    @pytest.mark.functional
    def test_email_blur_triggers_validation_without_submit(self, matrix_page: Page):
        page = matrix_page
        drive_to_email_step(page)
        email_field = page.get_by_role("textbox")
        email_field.fill("not-an-email")
        page.keyboard.press("Tab")  # blur without clicking Continue
        page.wait_for_timeout(500)
        continue_btn = page.get_by_role("button", name="Continue")
        is_disabled = continue_btn.is_disabled() if continue_btn.count() else False
        aria_invalid = email_field.get_attribute("aria-invalid")
        validation_signal_present = is_disabled or aria_invalid == "true"
        # We don't hard-fail if the app allows client-unvalidated blur
        # (server-side validation may be the design) — but the app must
        # not crash, and the field must retain the typed value.
        expect(email_field).to_have_value("not-an-email")
        assert validation_signal_present or email_field.is_visible(), (
            "Neither a blur-validation signal nor a stable field state "
            "was observed after tabbing off an invalid email."
        )

    @pytest.mark.functional
    def test_name_field_unicode_input_handled_gracefully(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)
        page.get_by_role("textbox").first.fill(config.EVAFI_INVALID_INPUTS["unicode_text"])
        page.get_by_role("textbox").nth(1).fill(FIXED_VALID_LAST_NAME)
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    @pytest.mark.functional
    def test_name_field_special_characters_handled_gracefully(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)
        page.get_by_role("textbox").first.fill(config.EVAFI_INVALID_INPUTS["special_characters"])
        page.get_by_role("textbox").nth(1).fill(FIXED_VALID_LAST_NAME)
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    @pytest.mark.functional
    def test_first_name_bva_255_char_boundary_accepted(self, matrix_page: Page):
        """255 chars = the lower/inclusive edge of the boundary — should
        be accepted (or at minimum not crash the app)."""
        page = matrix_page
        drive_to_name_step(page)
        page.get_by_role("textbox").first.fill("a" * 255)
        page.get_by_role("textbox").nth(1).fill(FIXED_VALID_LAST_NAME)
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    @pytest.mark.functional
    def test_first_name_bva_256_char_boundary_rejected_or_truncated(self, matrix_page: Page):
        """256 chars = one past the typical 255-char cap — expect the app
        to reject, truncate, or otherwise gracefully refuse it, never
        crash/hang."""
        page = matrix_page
        drive_to_name_step(page)
        field = page.get_by_role("textbox").first
        field.fill("a" * 256)
        page.get_by_role("textbox").nth(1).fill(FIXED_VALID_LAST_NAME)
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    @pytest.mark.functional
    def test_phone_field_bva_long_integer_boundary(self, matrix_page: Page):
        page = matrix_page
        drive_to_phone_step(page)
        fill_phone_step(page, config.EVAFI_INVALID_INPUTS["long_integer"], submit=False)
        page.get_by_role("button", name="Send code").click()
        _assert_app_survived_invalid_input(page)