"""
test_cross_browser_matrix_class.py
==================================
TestCrossBrowserMatrix — split out of the original monolithic test file so each test
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


class TestCrossBrowserMatrix:
    @pytest.mark.cross_browser
    def test_launcher_and_onboarding_flow_reaches_name_step(self, named_browser_page: Page, request):
        """Drives launcher -> branch resolution -> intro slides -> name
        step on whichever named browser this param currently is. Handles
        BOTH the pick-1-of-4 and pick-3-of-8 branches via the same
        branch-aware helpers the rest of the suite uses."""
        browser_name = request.node.callspec.params["named_browser_page"]
        page = named_browser_page
        open_chat_widget(page)
        branch = resolve_goal_or_balance_step(page)
        assert branch in ("pick_one_of_four", "pick_three_of_eight"), (
            f"Unrecognized branch on {browser_name}"
        )
        advance_through_intro_slides(page, branch)
        expect(page.get_by_role("textbox").first).to_be_visible()

    @pytest.mark.cross_browser
    def test_name_and_email_steps_work_on_named_browser(self, named_browser_page: Page, request):
        browser_name = request.node.callspec.params["named_browser_page"]
        page = named_browser_page
        open_chat_widget(page)
        branch = resolve_goal_or_balance_step(page)
        advance_through_intro_slides(page, branch)
        fill_name_step(page)  # FIXED_VALID_FIRST_NAME / FIXED_VALID_LAST_NAME
        fill_email_step(page)  # FIXED_VALID_EMAIL
        expect(page.get_by_role("button", name="Continue")).to_be_visible(), (
            f"Continue button missing after email step on {browser_name}"
        )


# ═════════════════════════════════════════════════════════════════════════
# 7. TestAdvancedSmoke — deeper smoke coverage beyond the one-test-per-
#    step baseline in TestSmoke: console-error hygiene, page metadata,
#    direct deep-link navigation, browser-back resilience, and
#    debt-tier button breadth. Each test independently reaches its own
#    step, same pattern as the rest of the suite.
# ═════════════════════════════════════════════════════════════════════════