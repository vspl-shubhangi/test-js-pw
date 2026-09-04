"""
test_smoke_class.py
===================
TestSmoke — split out of the original monolithic test file so each test
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


class TestSmoke:
    @pytest.mark.smoke
    def test_chat_launcher_visible_and_clickable(self, page: Page):
        page.goto(config.LOGIN_URL)
        page.wait_for_load_state("networkidle")
        _dismiss_cookie_notice_if_present(page)
        launcher = page.locator("#site-navbar").get_by_role("button", name="Chat with Eva")
        expect(launcher).to_be_visible()
        launcher.click()
        expect(page.get_by_role("button", name="Go forward")).to_be_visible()

    @pytest.mark.smoke
    def test_goal_or_balance_step_renders_after_go_forward(self, page: Page):
        open_chat_widget(page)
        branch = resolve_goal_or_balance_step(page)
        assert branch in ("pick_one_of_four", "pick_three_of_eight")
        advance_through_intro_slides(page, branch)
        expect(page.get_by_role("button", name="Continue")).to_be_visible()

    @pytest.mark.smoke
    def test_name_step_renders(self, page: Page):
        drive_to_name_step(page)
        expect(page.get_by_role("textbox").first).to_be_visible()
        expect(page.get_by_role("textbox").nth(1)).to_be_visible()

    @pytest.mark.smoke
    def test_email_step_renders(self, page: Page):
        drive_to_email_step(page)
        expect(page.get_by_role("textbox")).to_be_visible()

    @pytest.mark.smoke
    def test_debt_amount_step_renders(self, page: Page):
        drive_to_debt_amount_step(page)
        expect(page.get_by_role("button", name=DATA["debt_amount"])).to_be_visible()

    @pytest.mark.smoke
    def test_dob_step_renders(self, page: Page):
        drive_to_dob_step(page)
        expect(page.get_by_role("textbox").first).to_be_visible()
        expect(page.get_by_role("textbox").nth(1)).to_be_visible()
        expect(page.get_by_role("textbox").nth(2)).to_be_visible()

    @pytest.mark.smoke
    def test_phone_step_renders(self, page: Page):
        drive_to_phone_step(page)
        expect(page.get_by_role("textbox", name="(000) 000-")).to_be_visible()


# ═════════════════════════════════════════════════════════════════════════
# 2. TestEndToEnd — full realistic journeys
# ═════════════════════════════════════════════════════════════════════════