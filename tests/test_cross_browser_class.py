"""
test_cross_browser_class.py
===========================
TestCrossBrowser — split out of the original monolithic test file so each test
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


class TestCrossBrowser:
    @pytest.mark.cross_browser
    def test_launcher_and_branch_resolve_on_current_engine(self, page: Page, browser_engine: str):
        open_chat_widget(page)
        branch = resolve_goal_or_balance_step(page)
        assert branch in ("pick_one_of_four", "pick_three_of_eight"), (
            f"Unrecognized branch on engine={browser_engine}"
        )
        advance_through_intro_slides(page, branch)
        expect(page.get_by_role("button", name="Continue")).to_be_visible()

    @pytest.mark.cross_browser
    def test_name_and_email_steps_work_on_current_engine(self, page: Page, browser_engine: str):
        drive_to_email_step(page)
        fill_email_step(page)
        expect(page.get_by_role("button", name="Continue")).to_be_visible()


# ═════════════════════════════════════════════════════════════════════════
# 4. TestCrossDevice — parametrized by conftest.py's device_page fixture
# ═════════════════════════════════════════════════════════════════════════