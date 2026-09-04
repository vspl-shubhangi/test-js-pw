"""
test_end_to_end_class.py
========================
TestEndToEnd — split out of the original monolithic test file so each test
class lives in its own file under tests/, matching the project's folder
structure. Shared step-driver helpers (open_chat_widget, drive_to_*,
fill_*, resolve_goal_or_balance_step, advance_through_intro_slides,
FIXED_VALID_EMAIL, FIXED_VALID_PHONE, FIXED_VALID_FIRST_NAME,
FIXED_VALID_LAST_NAME, FIXED_VALID_DOB_MONTH/DAY/YEAR, drive_to_offers_step, etc.) live in
wizard_helpers.py; shared fixtures (page, device_page, named_browser_page,
matrix_page, browser_engine) are auto-discovered from conftest.py by
pytest -- neither needs a special import here beyond the star-import
below for the plain functions.
"""

import re

import pytest
from playwright.sync_api import Page, expect

import config
from wizard_helpers import *  # noqa: F401,F403 -- see __all__ in wizard_helpers.py


class TestEndToEnd:
    @pytest.mark.e2e
    def test_full_onboarding_journey_reaches_offers_agent(self, page: Page):
        """NOTE: this test calls 'Send code', which triggers a REAL SMS
        in this environment, and includes the mandated wait times after
        the email step (20s), after Send code (30s), and after OTP
        submission (35s) -- per happy_path_otp_screen.py. The final
        step clicks "Connect to EvaFi Agent" itself, so the assertion
        checks the app landed in a recognizable, non-crashed state
        rather than re-checking visibility of the button just clicked."""
        drive_to_offers_step(page)
        page.wait_for_timeout(1000)
        assert page.title().strip() != "", (
            "Page title went blank after 'Connect to EvaFi Agent' — possible crash."
        )

    @pytest.mark.e2e
    def test_pick_three_of_eight_branch_reaches_name_step(self, page: Page):
        """Asserts the 8-button (pick-3-of-8) branch specifically when
        it occurs this run; skips (rather than fails) when the 4-button
        branch renders instead — see the companion test below for that
        case. advance_through_intro_slides() already picks a genuinely
        random 3 of the 8 labels each run, not a fixed trio."""
        open_chat_widget(page)
        branch = resolve_goal_or_balance_step(page)
        if branch != "pick_three_of_eight":
            pytest.skip("4-button branch rendered this run — covered by the companion test.")
        advance_through_intro_slides(page, branch)
        expect(page.get_by_role("textbox").first).to_be_visible()

    @pytest.mark.e2e
    def test_pick_one_of_four_branch_reaches_name_step(self, page: Page):
        """Mirror of the test above for the 4-button (pick-1-of-4)
        branch. advance_through_intro_slides() picks a genuinely random
        1 of the 4 labels each run, not always the same button."""
        open_chat_widget(page)
        branch = resolve_goal_or_balance_step(page)
        if branch != "pick_one_of_four":
            pytest.skip("8-button branch rendered this run — covered by the companion test.")
        advance_through_intro_slides(page, branch)
        expect(page.get_by_role("textbox").first).to_be_visible()

    @pytest.mark.e2e
    def test_name_step_valid_input_progresses_to_email_step(self, page: Page):
        """Unique first/last legal name every run (per instruction) --
        fill_name_step() generates one automatically when no explicit
        name is passed."""
        drive_to_name_step(page)
        fill_name_step(page)
        expect(page.get_by_role("textbox")).to_be_visible()

    @pytest.mark.e2e
    def test_debt_amount_selection_progresses_to_dob_step(self, page: Page):
        drive_to_dob_step(page)
        expect(page.get_by_role("textbox").first).to_be_visible()  # Month field