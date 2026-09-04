"""
test_smoke_advanced_class.py
============================
TestSmokeAdvanced — split out of the original monolithic test file so each test
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


class TestSmokeAdvanced:
    """Advanced smoke coverage across the full device x browser matrix:
    console hygiene, layout overflow, and end-to-end stability."""

    @pytest.mark.smoke
    def test_no_console_errors_through_name_step(self, matrix_page: Page):
        page = matrix_page
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        drive_to_name_step(page)
        assert not console_errors, f"Console errors reaching the name step: {console_errors}"

    @pytest.mark.smoke
    def test_no_horizontal_page_overflow(self, matrix_page: Page):
        """Layout-overflow smoke check: the document shouldn't be wider
        than the viewport (a common mobile-responsiveness regression)."""
        page = matrix_page
        drive_to_name_step(page)
        viewport = page.viewport_size
        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        if viewport:
            assert scroll_width <= viewport["width"] + 5, (
                f"Horizontal overflow detected: scrollWidth={scroll_width} "
                f"> viewport width={viewport['width']}."
            )

    @pytest.mark.smoke
    def test_debt_amount_step_offers_multiple_tier_options(self, matrix_page: Page):
        page = matrix_page
        drive_to_debt_amount_step(page)
        amount_buttons = page.get_by_role("button", name=re.compile(r"^\$[\d,]+$"))
        assert amount_buttons.count() >= 2, "Expected multiple debt-amount tier buttons."

    @pytest.mark.smoke
    def test_no_failed_critical_network_requests_to_name_step(self, matrix_page: Page):
        page = matrix_page
        failed_requests = []
        page.on("requestfailed", lambda req: failed_requests.append(req.url))
        drive_to_name_step(page)
        assert not failed_requests, f"Failed network requests reaching the name step: {failed_requests}"


