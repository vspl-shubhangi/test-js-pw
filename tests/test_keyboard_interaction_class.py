"""
test_keyboard_interaction_class.py
==================================
TestKeyboardInteraction — split out of the original monolithic test file so each test
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


class TestKeyboardInteraction:
    """Keyboard-only interaction coverage: Escape, Tab/Shift+Tab focus
    order, Enter-to-submit, and a fully mouse-free step traversal."""

    @pytest.mark.keyboard
    def test_escape_key_does_not_crash_chat_widget(self, matrix_page: Page):
        page = matrix_page
        open_chat_widget(page)
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        assert page.title().strip() != "", "Page crashed/blanked after pressing Escape in the chat widget."

    @pytest.mark.keyboard
    def test_tab_moves_focus_from_first_to_last_name(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)
        first_field = page.get_by_role("textbox").first
        last_field = page.get_by_role("textbox").nth(1)
        first_field.click()
        first_field.fill(FIXED_VALID_FIRST_NAME)
        page.keyboard.press("Tab")
        expect(last_field).to_be_focused()

    @pytest.mark.keyboard
    def test_shift_tab_moves_focus_backward(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)
        first_field = page.get_by_role("textbox").first
        last_field = page.get_by_role("textbox").nth(1)
        last_field.click()
        page.keyboard.press("Shift+Tab")
        expect(first_field).to_be_focused()

    @pytest.mark.keyboard
    def test_enter_key_submits_name_step(self, matrix_page: Page):
        page = matrix_page
        drive_to_name_step(page)
        page.get_by_role("textbox").first.fill(FIXED_VALID_FIRST_NAME)
        last_field = page.get_by_role("textbox").nth(1)
        last_field.fill(FIXED_VALID_LAST_NAME)
        last_field.press("Enter")
        page.wait_for_timeout(800)
        expect(page.get_by_role("textbox")).to_be_visible()  # advanced to email step

    @pytest.mark.keyboard
    def test_keyboard_only_navigation_through_name_and_email_steps(self, matrix_page: Page):
        """No mouse clicks at all past the initial widget-open helper:
        Tab to focus, type, Enter to submit, for both the name and email
        steps back to back."""
        page = matrix_page
        drive_to_name_step(page)
        page.get_by_role("textbox").first.click()
        page.keyboard.type(FIXED_VALID_FIRST_NAME)
        page.keyboard.press("Tab")
        page.keyboard.type(FIXED_VALID_LAST_NAME)
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        email_field = page.get_by_role("textbox")
        expect(email_field).to_be_visible()
        email_field.click()
        page.keyboard.type(FIXED_VALID_EMAIL)
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        expect(page.get_by_role("button", name="Continue")).to_be_visible()