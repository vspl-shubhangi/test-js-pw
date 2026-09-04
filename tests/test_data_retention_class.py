"""
test_data_retention_class.py
============================
TestDataRetention — split out of the original monolithic test file so each test
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


class TestDataRetention:
    """Privacy/data-retention coverage: PII shouldn't linger client-side
    beyond what the current step needs, and shouldn't leak in plaintext
    into browser storage."""

    @pytest.mark.data_retention
    def test_name_fields_not_prefilled_from_prior_session_after_reload(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)
        first_name_value = FIXED_VALID_FIRST_NAME
        page.get_by_role("textbox").first.fill(first_name_value)
        page.get_by_role("textbox").nth(1).fill(FIXED_VALID_LAST_NAME)
        page.reload()
        page.wait_for_load_state("networkidle")
        # After a hard reload the wizard restarts from the homepage --
        # there should be no lingering chat-widget state with the typed
        # PII still sitting in a visible field.
        stray_prefilled = page.get_by_role("textbox").filter(has_text=first_name_value)
        assert stray_prefilled.count() == 0, (
            "First name value survived a full page reload — PII is "
            "being retained client-side longer than the active step."
        )

    @pytest.mark.data_retention
    def test_email_not_retained_in_local_or_session_storage(self, matrix_page: Page):
        page = matrix_page
        drive_to_email_step(page)
        fill_email_step(page)  # FIXED_VALID_EMAIL
        storage_dump = page.evaluate(
                "() => ({"
                "  local: JSON.stringify(window.localStorage),"
                "  session: JSON.stringify(window.sessionStorage)"
                "})"
        )
        combined = (storage_dump.get("local", "") + storage_dump.get("session", "")).lower()
        assert FIXED_VALID_EMAIL.lower() not in combined, (
            "Plaintext email address found in localStorage/sessionStorage "
            "— PII should not be retained unencrypted client-side."
        )

    @pytest.mark.data_retention
    def test_phone_not_retained_in_local_or_session_storage(self, matrix_page: Page):
        page = matrix_page
        drive_to_phone_step(page)
        fill_phone_step(page, FIXED_VALID_PHONE, submit=False)
        storage_dump = page.evaluate(
                "() => ({"
                "  local: JSON.stringify(window.localStorage),"
                "  session: JSON.stringify(window.sessionStorage)"
                "})"
        )
        combined = storage_dump.get("local", "") + storage_dump.get("session", "")
        digits_only = re.sub(r"\D", "", FIXED_VALID_PHONE)
        assert digits_only not in re.sub(r"\D", "", combined), (
            "Plaintext phone number found in localStorage/sessionStorage."
        )

    @pytest.mark.data_retention
    def test_fresh_context_does_not_inherit_previous_session_data(self, matrix_page: Page, playwright):
        """Drives real data into one context, closes it, opens a second
        FRESH context on the same browser, and confirms the new session
        starts with no residual state from the first."""
        first_page = matrix_page
        drive_to_name_step(first_page)
        first_name_value = FIXED_VALID_FIRST_NAME
        first_page.get_by_role("textbox").first.fill(first_name_value)
        first_browser = first_page.context.browser
        second_context = first_browser.new_context()
        second_page = second_context.new_page()
        try:
            drive_to_name_step(second_page)
            leaked = second_page.get_by_role("textbox").first.input_value()
            assert leaked == "" or leaked != first_name_value, (
                "A brand-new browser context inherited name-field data "
                "from a prior context/session."
            )
        finally:
            second_context.close()