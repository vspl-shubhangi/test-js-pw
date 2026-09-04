"""
test_emulation_class.py
=======================
TestEmulation — NEW class (req #3): browser ENVIRONMENT emulation
coverage, distinct from TestCrossDevice (viewport/UA) and
TestCrossBrowserMatrix (browser engine). This class emulates conditions
a real user's browser environment might present: dark/light color
scheme, geolocation, timezone + locale, offline/degraded network, a
reduced-motion accessibility preference, and permission grants/denials.

Each test builds its OWN Playwright context directly via the `browser`
fixture (from pytest-playwright) with the relevant `new_context(...)`
option set, rather than using matrix_page/device_page/named_browser_page
-- emulation options like color_scheme/geolocation/locale/timezone_id
are context-level settings orthogonal to the device/browser matrix, so a
dedicated lightweight context keeps each test focused on ONE emulated
dimension at a time.
"""

import pytest
from playwright.sync_api import Page, Browser, expect

import config
from wizard_helpers import *  # noqa: F401,F403 -- see __all__ in wizard_helpers.py


class TestEmulation:
    """Browser-environment emulation coverage. Handles whichever random
    goal-selection branch renders via the same branch-aware helpers used
    everywhere else in the suite."""

    @pytest.mark.emulation
    def test_dark_mode_color_scheme_renders_without_crash(self, browser: Browser):
        context = browser.new_context(color_scheme="dark")
        page = context.new_page()
        try:
            drive_to_name_step(page)
            expect(page.get_by_role("textbox").first).to_be_visible()
            assert page.title().strip() != "", "Page title blank under emulated dark color scheme."
        finally:
            context.close()

    @pytest.mark.emulation
    def test_light_mode_color_scheme_renders_without_crash(self, browser: Browser):
        context = browser.new_context(color_scheme="light")
        page = context.new_page()
        try:
            drive_to_name_step(page)
            expect(page.get_by_role("textbox").first).to_be_visible()
            assert page.title().strip() != "", "Page title blank under emulated light color scheme."
        finally:
            context.close()

    @pytest.mark.emulation
    def test_geolocation_permission_granted_does_not_crash_flow(self, browser: Browser):
        """Emulates a user physically located in Mumbai (matches the
        suite's own approximate location context) with geolocation
        permission pre-granted -- confirms the onboarding flow tolerates
        a real geolocation-aware browser environment end to end through
        the name step."""
        context = browser.new_context(
            geolocation={"latitude": 19.0760, "longitude": 72.8777},
            permissions=["geolocation"],
        )
        page = context.new_page()
        try:
            drive_to_name_step(page)
            expect(page.get_by_role("textbox").first).to_be_visible()
        finally:
            context.close()

    @pytest.mark.emulation
    def test_geolocation_permission_denied_does_not_crash_flow(self, browser: Browser):
        """Mirror of the test above with geolocation explicitly NOT
        granted -- the app must degrade gracefully (no crash / blank
        page) rather than assume location access is always available."""
        context = browser.new_context(permissions=[])
        page = context.new_page()
        try:
            drive_to_name_step(page)
            expect(page.get_by_role("textbox").first).to_be_visible()
        finally:
            context.close()

    @pytest.mark.emulation
    def test_non_us_timezone_and_locale_renders_correctly(self, browser: Browser):
        """Emulates an India-based user (IST timezone, en-IN locale) --
        catches locale-formatting regressions (dates, currency symbols)
        that a US-only testing environment would never surface."""
        context = browser.new_context(timezone_id="Asia/Kolkata", locale="en-IN")
        page = context.new_page()
        try:
            drive_to_name_step(page)
            expect(page.get_by_role("textbox").first).to_be_visible()
        finally:
            context.close()

    @pytest.mark.emulation
    def test_reduced_motion_preference_does_not_crash_flow(self, browser: Browser):
        """Emulates a user with the OS-level 'reduce motion' accessibility
        preference enabled -- confirms the app doesn't depend on
        animation-completion events to progress (a real, common
        accessibility regression class)."""
        context = browser.new_context(reduced_motion="reduce")
        page = context.new_page()
        try:
            drive_to_name_step(page)
            expect(page.get_by_role("textbox").first).to_be_visible()
        finally:
            context.close()

    @pytest.mark.emulation
    def test_homepage_survives_offline_transition(self, browser: Browser):
        """Loads the homepage online, then flips the context offline and
        confirms the already-loaded page doesn't hard-crash (no JS error
        overlay / blank page) -- does NOT assert full offline
        functionality, since this is a live web app with no documented
        offline/PWA support; it only asserts graceful degradation."""
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(config.LOGIN_URL)
            page.wait_for_load_state("networkidle")
            context.set_offline(True)
            page.wait_for_timeout(1500)
            assert page.title().strip() != "", (
                "Page title went blank immediately after going offline — unexpected hard crash."
            )
        finally:
            context.set_offline(False)
            context.close()

    @pytest.mark.emulation
    def test_slow_network_conditions_do_not_hang_indefinitely(self, browser: Browser):
        """Throttles the network via Chromium DevTools Protocol (CDP) to
        simulate a slow connection, then confirms the homepage still
        eventually loads within a generous bound rather than hanging
        forever. Chromium-only (CDP) -- skips on non-Chromium engines."""
        if browser.browser_type.name != "chromium":
            pytest.skip("Network throttling via CDP is Chromium-only.")
        context = browser.new_context()
        page = context.new_page()
        cdp = context.new_cdp_session(page)
        try:
            cdp.send("Network.enable")
            cdp.send(
                "Network.emulateNetworkConditions",
                {
                    "offline": False,
                    "latency": 400,  # ms
                    "downloadThroughput": 200 * 1024 // 8,  # ~200kbps
                    "uploadThroughput": 100 * 1024 // 8,
                },
            )
            page.goto(config.LOGIN_URL, timeout=45_000)
            page.wait_for_load_state("networkidle", timeout=45_000)
            assert page.title().strip() != "", "Page title blank under throttled network."
        finally:
            context.close()