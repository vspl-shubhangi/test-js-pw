"""
test_security_class.py
======================
TestSecurity — split out of the original monolithic test file so each test
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


class TestSecurity:
    """SQL-injection and XSS coverage, run through the same textbox
    surfaces as TestFunctional but with adversarial payloads."""

    @pytest.mark.security
    def test_sql_injection_boolean_based_payload_survives(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)
        page.get_by_role("textbox").first.fill("' OR '1'='1' -- ")
        page.get_by_role("textbox").nth(1).fill(FIXED_VALID_LAST_NAME)
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    @pytest.mark.security
    def test_sql_injection_union_based_payload_survives(self, matrix_page: Page):
        page = matrix_page
        drive_to_email_step(page)
        page.get_by_role("textbox").fill("x' UNION SELECT NULL,NULL,NULL-- -@evafi.test")
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    @pytest.mark.security
    def test_sql_injection_stacked_query_payload_survives(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)
        page.get_by_role("textbox").first.fill(FIXED_VALID_FIRST_NAME)
        page.get_by_role("textbox").nth(1).fill("'; DROP TABLE users;--")
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    @pytest.mark.security
    def test_xss_script_tag_payload_is_neutralized(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)

        def _submit():
            page.get_by_role("textbox").first.fill("<script>alert('XSS')</script>")
            page.get_by_role("textbox").nth(1).fill(FIXED_VALID_LAST_NAME)
            page.get_by_role("button", name="Continue").click()

        _assert_no_js_dialog_fires(page, _submit)
        _assert_app_survived_invalid_input(page)

    @pytest.mark.security
    def test_xss_image_onerror_payload_is_neutralized(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)

        def _submit():
            page.get_by_role("textbox").first.fill('<img src=x onerror=alert(1)>')
            page.get_by_role("textbox").nth(1).fill(FIXED_VALID_LAST_NAME)
            page.get_by_role("button", name="Continue").click()

        _assert_no_js_dialog_fires(page, _submit)
        _assert_app_survived_invalid_input(page)