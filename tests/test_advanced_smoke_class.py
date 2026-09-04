"""
test_advanced_smoke_class.py
============================
TestAdvancedSmoke — split out of the original monolithic test file so each test
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


class TestAdvancedSmoke:
    @pytest.mark.smoke
    def test_no_console_errors_on_homepage_load(self, page: Page):
        console_errors = []
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
        )
        page.goto(config.LOGIN_URL)
        page.wait_for_load_state("networkidle")
        _dismiss_cookie_notice_if_present(page)
        assert not console_errors, f"Console errors on homepage load: {console_errors}"

    @pytest.mark.smoke
    def test_homepage_has_nonempty_title(self, page: Page):
        page.goto(config.LOGIN_URL)
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Homepage <title> is empty."

    @pytest.mark.smoke
    def test_viewport_meta_tag_present_for_mobile_friendliness(self, page: Page):
        page.goto(config.LOGIN_URL)
        page.wait_for_load_state("networkidle")
        viewport_meta = page.locator('meta[name="viewport"]')
        assert viewport_meta.count() > 0, (
            "No <meta name='viewport'> tag found on homepage — page may "
            "not render correctly on mobile devices."
        )

    @pytest.mark.smoke
    def test_debt_amount_step_offers_multiple_tier_options(self, page: Page):
        """Goes beyond test_debt_amount_step_renders (which only checks
        the one tier the rest of the suite happens to use): confirms the
        debt-selection screen genuinely offers several distinct amount
        buttons, not just the single hardcoded one in config.py."""
        drive_to_debt_amount_step(page)
        amount_buttons = page.get_by_role("button", name=re.compile(r"^\$[\d,]+$"))
        count = amount_buttons.count()
        assert count >= 2, f"Expected multiple debt-amount tier buttons, found {count}."

    @pytest.mark.smoke
    def test_browser_back_after_name_step_does_not_crash(self, page: Page):
        drive_to_name_step(page)
        page.go_back()
        page.wait_for_timeout(800)
        assert page.title().strip() != "", (
            "Page crashed/blanked after browser back navigation from the name step."
        )

    @pytest.mark.smoke
    def test_direct_navigation_to_onboarding_url_does_not_error(self, page: Page):
        """Exercises config.EVAFI_ONBOARDING_URL (previously
        informational-only — see config.py) to confirm deep-linking
        straight into the onboarding flow doesn't hard-crash, even if
        the app just redirects back to the homepage/launcher."""
        response = page.goto(config.EVAFI_ONBOARDING_URL)
        page.wait_for_load_state("networkidle")
        status = response.status if response else None
        assert status is None or status < 500, (
            f"Direct navigation to {config.EVAFI_ONBOARDING_URL} returned "
            f"server error status: {status}"
        )
        assert page.title().strip() != "", "Page title blank after direct onboarding-URL navigation."


# ═════════════════════════════════════════════════════════════════════════
# 8-13. FULL DEVICE x BROWSER MATRIX CONTENT CLASSES
# All six classes below take `matrix_page` (see fixture above), so pytest
# runs EVERY test in EVERY class once per device x browser combination —
# smartphone(Android/iPhone) x tablet(Android/iPhone) x desktop, each
# times chrome/firefox/brave/msedge = 20 runs per test. All classes use
# the existing branch-aware drive_to_* helpers, so the random 3-option /
# 1-option screen is already handled correctly everywhere here.
# ═════════════════════════════════════════════════════════════════════════


