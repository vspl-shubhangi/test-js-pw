"""
tests/test_evafi_onboarding.py
================================
Evafi onboarding-wizard test suite — single-file version (navigation
helpers + all test classes together). Only config.py, conftest.py, and
pytest.ini remain as separate files this suite depends on.

ARCHITECTURE NOTES
------------------
- Uses pytest-playwright's function-scoped `page` fixture (fresh browser
  context per test, per conftest.py / pytest.ini) — every test drives the
  flow from the homepage itself via the drive_to_* helpers below. There
  is no shared session state to resume from.

- WHY EVERY drive_to_* HELPER RE-RUNS THE WHOLE FLOW FROM THE HOMEPAGE:
  the `page` fixture is function-scoped (a brand-new browser context per
  test), so there is no state to resume from — each test independently
  reaches its own target step. This is deliberate, not an inefficiency:
  it's what lets every test run in isolation/any order and under any of
  the parametrized device/browser configurations in conftest.py.

- BRANCH HANDLING: Evafi renders one of two different screens right after
  'Go forward' — non-deterministically:
    * "goal_selection": 3 independent buttons, ALL THREE must be clicked
      ("Cut my interest costs", "Lower my monthly payment",
      "Pay off debt sooner").
    * "single_choice": exactly 1 button ("My balances barely go down").
  resolve_goal_or_balance_step() below detects which one rendered THIS
  run and drives it to completion either way. Downstream navigation
  DIVERGES right after this point: "goal_selection" needs 3x "Next"
  clicks before "Continue" (one on the same screen, two more to advance
  the intro slides), while "single_choice" needs only 1x "Next" click
  (the option click itself already advances the screen) — see
  advance_through_intro_slides() for the branch-aware handling. Once
  past "Continue", the rest of the flow (name/email/debt/DOB/phone/OTP)
  is identical regardless of which branch occurred.

- CROSS-BROWSER coverage is achieved by re-running this file with
  different --browser CLI flags (chromium/firefox/webkit), NOT by
  parametrizing engines inside one run — this matches conftest.py's
  `browser_engine` fixture, which is a session-scoped STRING (whichever
  engine was passed on the CLI), not a fixture that launches multiple
  engines. Example:
      pytest --browser chromium
      pytest --browser firefox
      pytest --browser webkit

- CROSS-DEVICE coverage uses conftest.py's parametrized `device_page`
  fixture (desktop/tablet/mobile) — TestCrossDevice re-runs the critical
  path once per device profile automatically; no manual parametrize
  needed in the test body.

- SEQUENCING: the "Chat with Eva" launcher (step 0) is tested in EXACTLY
  ONE place — TestSmoke.test_chat_launcher_visible_and_clickable. No
  other class re-asserts anything about the homepage/launcher; every
  other test starts its own assertions from the goal/balance step onward,
  reflecting the real page sequence a user experiences.

- TestRegression is the field-by-field negative-input matrix (SQL
  injection, long string upper/lower, long integer, special characters,
  unicode) applied to EVERY text field in the wizard, executed in
  navigation-sequence order: first/last name -> email -> phone. Each
  parametrized case independently drives to its field's step, submits
  the edge-case payload, and asserts the app lands in a recognizable
  state (either validation blocked it, or it was accepted and the wizard
  advanced) rather than crashing or hanging.
"""

import os
import re

import pytest
from playwright.sync_api import Page, expect

import config

DATA = config.EVAFI_TEST_DATA
INVALID_CASES = list(config.EVAFI_INVALID_INPUTS.items())
INVALID_IDS = list(config.EVAFI_INVALID_INPUTS.keys())

GOAL_SELECTION_LABELS = (
    "Cut my interest costs",
    "Lower my monthly payment",
    "Pay off debt sooner",
)
SINGLE_CHOICE_LABEL = "My balances barely go down"


# ═════════════════════════════════════════════════════════════════════════
# NAVIGATION HELPERS
# ═════════════════════════════════════════════════════════════════════════

# ── Step 0 — Homepage / chat launcher ──────────────────────────────────
# (tested by exactly ONE class below: TestSmoke — every downstream helper
#  assumes that step is already proven and does not re-assert anything
#  about the homepage itself)


def _dismiss_cookie_notice_if_present(page: Page) -> None:
    """Cookie-notice ordering isn't guaranteed relative to the chat
    launcher click across runs (observed both before and after in
    different captures) — check for it defensively wherever it might
    appear rather than assuming a fixed position in the sequence."""
    close_btn = page.get_by_role("button", name="Close cookie notice")
    try:
        close_btn.wait_for(state="visible", timeout=2500)
        close_btn.click()
    except Exception:
        pass  # notice didn't appear this run — nothing to dismiss


def _click_chat_launcher(page: Page) -> None:
    """Locates & clicks the 'Chat with Eva' launcher.

    On desktop/tablet viewports it lives inside #site-navbar (the
    original captures). On mobile viewports it does NOT — see the
    three_opt_mob_view.py capture, which clicks an UNSCOPED
    `get_by_role("button", name="Chat with Eva").first` instead. This is
    what caused every TestCrossDevice[mobile-*] test to time out: they
    were all waiting 30s on a locator scoped to #site-navbar that never
    resolves on the mobile layout (the navbar collapses / the launcher
    renders outside it, and on some runs the goto even lands on a
    different marketing domain entirely).

    Strategy: try the desktop-scoped locator first (fast path, matches
    every already-passing desktop/tablet run) and fall back to the
    unscoped mobile-capture locator if it doesn't appear in time.
    """
    navbar_launcher = page.locator("#site-navbar").get_by_role("button", name="Chat with Eva")
    try:
        navbar_launcher.wait_for(state="visible", timeout=6000)
        navbar_launcher.click()
        return
    except Exception:
        pass
    # Desktop-scoped locator didn't resolve -> mobile layout instead.
    page.get_by_role("button", name="Chat with Eva").first.click()


def _click_intro_advance_button(page: Page) -> None:
    """The button right after the launcher click is labeled 'Go forward'
    on desktop/tablet captures but 'Let's get started' on the mobile
    capture (three_opt_mob_view.py) — same step, different copy per
    viewport. Click whichever one actually renders."""
    go_forward_btn = page.get_by_role("button", name="Go forward")
    try:
        go_forward_btn.wait_for(state="visible", timeout=6000)
        go_forward_btn.click()
        return
    except Exception:
        pass
    page.get_by_role("button", name="Let's get started").click()


def open_chat_widget(page: Page) -> None:
    """Homepage -> chat widget -> first intro-advance click. Responsive
    across desktop/tablet/mobile — see _click_chat_launcher() and
    _click_intro_advance_button() above for why a single unconditional
    locator/label doesn't work on every viewport."""
    page.goto(config.LOGIN_URL)
    page.wait_for_load_state("networkidle")
    _dismiss_cookie_notice_if_present(page)
    _click_chat_launcher(page)
    _dismiss_cookie_notice_if_present(page)
    _click_intro_advance_button(page)


# ── The non-deterministic branch ───────────────────────────────────────


def resolve_goal_or_balance_step(page: Page) -> str:
    """
    Handles Evafi's non-deterministic branch immediately after
    'Go forward'. Detects which of the two screens rendered THIS run and
    drives it to completion:

      - "goal_selection": 3 independent buttons — ALL THREE must be
        clicked (order does not matter to the app).
      - "single_choice":  exactly 1 button, 'My balances barely go down'.

    Returns which branch was taken so callers/assertions can log it or
    (as TestEndToEnd does) assert branch-specific behavior when that
    branch happens to occur, without failing the run when the other
    branch shows up instead.
    """
    single_choice_btn = page.get_by_role("button", name=SINGLE_CHOICE_LABEL)
    try:
        single_choice_btn.wait_for(state="visible", timeout=4000)
        single_choice_btn.click()
        return "single_choice"
    except Exception:
        pass

    # Single-choice button never appeared within the timeout -> this run
    # rendered the 3-button goal-selection screen instead.
    for label in GOAL_SELECTION_LABELS:
        page.get_by_role("button", name=label).click()
    return "goal_selection"


def advance_through_intro_slides(page: Page, branch: str) -> None:
    """Next-click count is NOT identical across branches — it depends on
    which screen resolve_goal_or_balance_step() just resolved:

      - "goal_selection" (3-button screen): after all three options are
        clicked, the app stays on that SAME screen and still needs a
        "Next" click there, followed by 2 more "Next" clicks to advance
        through the remaining intro slides. Total: 3x Next, then Continue.
        (Confirmed against three_options_button_script.py capture.)

      - "single_choice" (1-button screen): clicking the single option
        button itself navigates to the next screen already, so only 1
        "Next" click remains before Continue. Total: 1x Next, then
        Continue. (Confirmed against one_option_button_script.py capture.)

    Using a fixed count of 3 regardless of branch is what caused the
    single_choice run to time out: it left the test waiting on a "Next"
    button that no longer existed (it was already on the Continue-button
    page after the 1st Next click).
    """
    next_clicks = 3 if branch == "goal_selection" else 1
    for _ in range(next_clicks):
        page.get_by_role("button", name="Next").click()
    page.get_by_role("button", name="Continue").click()


# ── Cumulative drive_to_* helpers — each one reaches exactly one step ──


def drive_to_name_step(page: Page) -> None:
    open_chat_widget(page)
    branch = resolve_goal_or_balance_step(page)
    advance_through_intro_slides(page, branch)


def fill_name_step(page: Page, first_name: str, last_name: str, submit: bool = True) -> None:
    page.get_by_role("textbox").first.fill(first_name)
    page.get_by_role("textbox").nth(1).fill(last_name)
    if submit:
        page.get_by_role("button", name="Continue").click()


def drive_to_email_step(page: Page) -> None:
    drive_to_name_step(page)
    fill_name_step(page, DATA["first_name"], DATA["last_name"])


def fill_email_step(page: Page, email: str, submit: bool = True) -> None:
    page.get_by_role("textbox").fill(email)
    if submit:
        page.get_by_role("button", name="Continue").click()


def drive_to_debt_amount_step(page: Page) -> None:
    drive_to_email_step(page)
    fill_email_step(page, DATA["email"])
    page.get_by_role("button", name="Continue").click()  # 2nd Continue after email (info screen)


def select_debt_amount(page: Page, label: str) -> None:
    page.get_by_role("button", name=label).click()
    for _ in range(3):
        page.get_by_role("button", name="Continue").click()


def drive_to_dob_step(page: Page) -> None:
    drive_to_debt_amount_step(page)
    select_debt_amount(page, DATA["debt_amount"])


def fill_dob_step(page: Page, month: str, day: str, year: str, submit: bool = True) -> None:
    page.get_by_role("textbox").first.fill(month)
    page.get_by_role("textbox").nth(1).fill(day)
    page.get_by_role("textbox").nth(2).fill(year)
    if submit:
        page.get_by_role("button", name="Continue").click()


def drive_to_phone_step(page: Page) -> None:
    drive_to_dob_step(page)
    fill_dob_step(page, DATA["dob_month"], DATA["dob_day"], DATA["dob_year"])


def fill_phone_step(page: Page, phone: str, submit: bool = True) -> None:
    page.get_by_role("textbox", name="(000) 000-").fill(phone)
    if submit:
        page.get_by_role("button", name="Send code").click()


def drive_to_otp_step(page: Page) -> None:
    """Reaches the OTP screen. NOTE: this calls 'Send code', which
    triggers a REAL SMS in this environment. Use sparingly — reserved for
    the single dedicated full-journey E2E test below, not for every
    regression test that merely wants to reach the phone field."""
    drive_to_phone_step(page)
    fill_phone_step(page, DATA["phone_display"])


def fill_otp_step(page: Page, digits) -> None:
    boxes = page.locator("div:nth-child(5) > div > div > input")
    for i, digit in enumerate(digits):
        boxes.nth(i).fill(digit)
    page.get_by_role("button", name="Continue").click()


# ── Shared assertion for the negative-input matrix ─────────────────────


def _assert_app_survived_invalid_input(page: Page) -> None:
    """After submitting an edge-case payload, the app must land in a
    RECOGNIZABLE state: either it's still showing at least one input
    control (validation blocked the payload / same step) or it advanced
    and is showing at least one button (payload was accepted as literal
    text and the wizard moved on). Either outcome is acceptable — a
    genuine regression looks like NEITHER: a blank page, a JS error
    overlay, or a hang, which is what this guards against."""
    page.wait_for_timeout(800)
    has_textbox = page.get_by_role("textbox").count() > 0
    has_button = page.get_by_role("button").count() > 0
    assert has_textbox or has_button, (
        "Page shows neither an input nor a button after submitting the "
        "payload — possible crash, blank page, or unhandled JS error."
    )
    assert page.title().strip() != "", "Page title went blank — possible crash."


# ═════════════════════════════════════════════════════════════════════════
# 1. TestSmoke — one test per step, in page-sequence order.
#    Step 0 (launcher) lives ONLY here.
# ═════════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════════
# NAMED-BROWSER FIXTURE — launches a SPECIFIC browser/channel directly,
# independent of the --browser CLI flag, so TestCrossBrowserMatrix can
# cover chrome/chromium/firefox/brave/msedge in ONE pytest run instead of
# requiring 5 separate CLI invocations (that's what TestCrossBrowser
# above is for instead).
# ═════════════════════════════════════════════════════════════════════════

NAMED_BROWSER_LAUNCH_CONFIG = {
    "chromium": {"engine": "chromium", "channel": None},
    "chrome":   {"engine": "chromium", "channel": "chrome"},
    "msedge":   {"engine": "chromium", "channel": "msedge"},
    "firefox":  {"engine": "firefox",  "channel": None},
    # Brave has no official Playwright "channel" — it's Chromium under
    # the hood, so it's launched via an explicit executable_path instead.
    "brave":    {"engine": "chromium", "channel": None, "needs_brave_path": True},
}

# Common install locations checked when BRAVE_EXECUTABLE_PATH isn't set.
_BRAVE_DEFAULT_PATHS = [
    "/usr/bin/brave-browser",
    "/usr/bin/brave",
    "/snap/bin/brave",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
]


def _resolve_brave_executable() -> "str | None":
    custom = os.getenv("BRAVE_EXECUTABLE_PATH")
    if custom and os.path.exists(custom):
        return custom
    for candidate in _BRAVE_DEFAULT_PATHS:
        if os.path.exists(candidate):
            return candidate
    return None


@pytest.fixture(
    params=list(NAMED_BROWSER_LAUNCH_CONFIG.keys()),
    ids=list(NAMED_BROWSER_LAUNCH_CONFIG.keys()),
)
def named_browser_page(request, playwright):
    """Function-scoped Page launched against ONE specific named browser.

    Unlike conftest.py's session-scoped `browser`/`browser_engine`
    (driven entirely by the --browser CLI flag), this fixture launches
    its own browser per param so a single pytest run can exercise all
    five entries in NAMED_BROWSER_LAUNCH_CONFIG back to back.

    Brave / any browser missing locally SKIPS (not fails) with a message
    telling you how to point at it, so an incomplete local/CI browser
    install doesn't red the whole suite.
    """
    name = request.param
    cfg = NAMED_BROWSER_LAUNCH_CONFIG[name]
    engine = getattr(playwright, cfg["engine"])

    launch_kwargs = {"headless": False}
    if cfg.get("channel"):
        launch_kwargs["channel"] = cfg["channel"]
    if cfg.get("needs_brave_path"):
        brave_path = _resolve_brave_executable()
        if not brave_path:
            pytest.skip(
                "Brave executable not found locally. Install Brave, or "
                "set BRAVE_EXECUTABLE_PATH to its binary path, to "
                "include Brave in the cross-browser matrix."
            )
        launch_kwargs["executable_path"] = brave_path

    try:
        browser = engine.launch(**launch_kwargs)
    except Exception as exc:
        pytest.skip(f"Could not launch '{name}': {exc}")
        return

    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()
    browser.close()


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
        assert branch in ("goal_selection", "single_choice")
        expect(page.get_by_role("button", name="Next")).to_be_visible()

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


class TestEndToEnd:
    @pytest.mark.e2e
    def test_full_onboarding_journey_reaches_otp_screen(self, page: Page):
        """NOTE: this test calls 'Send code', which triggers a REAL SMS in
        this environment. It stops at verifying the OTP screen renders —
        it does not assume/hardcode a real OTP value."""
        drive_to_otp_step(page)
        otp_boxes = page.locator("div:nth-child(5) > div > div > input")
        expect(otp_boxes.first).to_be_visible()
        assert otp_boxes.count() == 6

    @pytest.mark.e2e
    def test_goal_selection_branch_reaches_name_step(self, page: Page):
        """Asserts the 3-button branch specifically when it occurs this
        run; skips (rather than fails) when the single-choice branch
        renders instead — see the companion test below for that case."""
        open_chat_widget(page)
        branch = resolve_goal_or_balance_step(page)
        if branch != "goal_selection":
            pytest.skip("Single-choice branch rendered this run — covered by the companion test.")
        advance_through_intro_slides(page, branch)
        expect(page.get_by_role("textbox").first).to_be_visible()

    @pytest.mark.e2e
    def test_single_choice_branch_reaches_name_step(self, page: Page):
        """Mirror of the test above for the single-button branch."""
        open_chat_widget(page)
        branch = resolve_goal_or_balance_step(page)
        if branch != "single_choice":
            pytest.skip("Goal-selection branch rendered this run — covered by the companion test.")
        advance_through_intro_slides(page, branch)
        expect(page.get_by_role("textbox").first).to_be_visible()

    @pytest.mark.e2e
    def test_name_step_valid_input_progresses_to_email_step(self, page: Page):
        drive_to_name_step(page)
        fill_name_step(page, DATA["first_name"], DATA["last_name"])
        expect(page.get_by_role("textbox")).to_be_visible()

    @pytest.mark.e2e
    def test_debt_amount_selection_progresses_to_dob_step(self, page: Page):
        drive_to_dob_step(page)
        expect(page.get_by_role("textbox").first).to_be_visible()  # Month field


# ═════════════════════════════════════════════════════════════════════════
# 3. TestCrossBrowser — same run, tagged with whichever engine the CLI
#    --browser flag selected. Run this file 3x (chromium/firefox/webkit)
#    for full cross-browser coverage — see module docstring.
# ═════════════════════════════════════════════════════════════════════════


class TestCrossBrowser:
    @pytest.mark.cross_browser
    def test_launcher_and_branch_resolve_on_current_engine(self, page: Page, browser_engine: str):
        open_chat_widget(page)
        branch = resolve_goal_or_balance_step(page)
        assert branch in ("goal_selection", "single_choice"), (
            f"Unrecognized branch on engine={browser_engine}"
        )
        expect(page.get_by_role("button", name="Next")).to_be_visible()

    @pytest.mark.cross_browser
    def test_name_and_email_steps_work_on_current_engine(self, page: Page, browser_engine: str):
        drive_to_email_step(page)
        fill_email_step(page, DATA["email"])
        expect(page.get_by_role("button", name="Continue")).to_be_visible()


# ═════════════════════════════════════════════════════════════════════════
# 4. TestCrossDevice — parametrized by conftest.py's device_page fixture
# ═════════════════════════════════════════════════════════════════════════


class TestCrossDevice:
    @pytest.mark.cross_device
    def test_launcher_and_branch_resolve_on_device(self, device_page: Page):
        open_chat_widget(device_page)
        branch = resolve_goal_or_balance_step(device_page)
        assert branch in ("goal_selection", "single_choice")
        expect(device_page.get_by_role("button", name="Next")).to_be_visible()

    @pytest.mark.cross_device
    def test_name_step_fillable_on_device(self, device_page: Page):
        drive_to_name_step(device_page)
        first = device_page.get_by_role("textbox").first
        first.fill(DATA["first_name"])
        expect(first).to_have_value(DATA["first_name"])

    @pytest.mark.cross_device
    def test_phone_field_visible_and_usable_on_device(self, device_page: Page):
        drive_to_phone_step(device_page)
        phone_field = device_page.get_by_role("textbox", name="(000) 000-")
        expect(phone_field).to_be_visible()
        phone_field.fill(DATA["phone_display"])
        expect(phone_field).to_have_value(DATA["phone_display"])


# ═════════════════════════════════════════════════════════════════════════
# 5. TestRegression — field-by-field negative-input matrix, executed in
#    navigation-sequence order: first name -> last name -> email -> phone.
# ═════════════════════════════════════════════════════════════════════════


class TestRegression:

    # ── First legal name ──────────────────────────────────────────────
    @pytest.mark.regression
    @pytest.mark.parametrize("case_name,payload", INVALID_CASES, ids=INVALID_IDS)
    def test_first_name_field_survives_invalid_input(self, page: Page, case_name, payload):
        drive_to_name_step(page)
        page.get_by_role("textbox").first.fill(payload)
        page.get_by_role("textbox").nth(1).fill(DATA["last_name"])
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    # ── Last legal name ───────────────────────────────────────────────
    @pytest.mark.regression
    @pytest.mark.parametrize("case_name,payload", INVALID_CASES, ids=INVALID_IDS)
    def test_last_name_field_survives_invalid_input(self, page: Page, case_name, payload):
        drive_to_name_step(page)
        page.get_by_role("textbox").first.fill(DATA["first_name"])
        page.get_by_role("textbox").nth(1).fill(payload)
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    # ── Email ─────────────────────────────────────────────────────────
    @pytest.mark.regression
    @pytest.mark.parametrize("case_name,payload", INVALID_CASES, ids=INVALID_IDS)
    def test_email_field_survives_invalid_input(self, page: Page, case_name, payload):
        drive_to_email_step(page)
        page.get_by_role("textbox").fill(payload)
        page.get_by_role("button", name="Continue").click()
        _assert_app_survived_invalid_input(page)

    # ── Phone number ──────────────────────────────────────────────────
    # NOTE: we deliberately do NOT click "Send code" for these payloads —
    # that button triggers a REAL SMS, and none of these payloads are
    # plausible phone numbers. We only verify the masked field itself
    # stays stable (accepts/rejects/truncates the payload without
    # crashing the page), not the send-code round trip.
    @pytest.mark.regression
    @pytest.mark.parametrize("case_name,payload", INVALID_CASES, ids=INVALID_IDS)
    def test_phone_field_survives_invalid_input(self, page: Page, case_name, payload):
        drive_to_phone_step(page)
        phone_field = page.get_by_role("textbox", name="(000) 000-")
        phone_field.fill(payload)
        page.wait_for_timeout(500)
        expect(phone_field).to_be_visible()
        assert page.title().strip() != ""

    @pytest.mark.regression
    def test_phone_field_rejects_too_many_digits(self, page: Page):
        """Dedicated boundary case: a real malformed value observed during
        manual capture (11 digits instead of 10) should not be silently
        accepted as a valid, sendable phone number."""
        drive_to_phone_step(page)
        phone_field = page.get_by_role("textbox", name="(000) 000-")
        phone_field.fill(config.EVAFI_PHONE_TOO_MANY_DIGITS)
        send_btn = page.get_by_role("button", name="Send code")
        if send_btn.is_enabled():
            value = phone_field.input_value()
            assert value != config.EVAFI_PHONE_TOO_MANY_DIGITS or len(value) <= len(DATA["phone_display"]), (
                "Phone field accepted an 11-digit value verbatim with no "
                "masking/truncation/validation."
            )


# ═════════════════════════════════════════════════════════════════════════
# 6. TestCrossBrowserMatrix — chrome, chromium, firefox, brave, msedge, all
#    in ONE pytest run via the named_browser_page fixture above. This is
#    additive to TestCrossBrowser (which relies on re-running the file
#    with different --browser CLI flags) — it doesn't replace it.
# ═════════════════════════════════════════════════════════════════════════


class TestCrossBrowserMatrix:
    @pytest.mark.cross_browser
    def test_launcher_and_onboarding_flow_reaches_name_step(self, named_browser_page: Page, request):
        """Drives launcher -> branch resolution -> intro slides -> name
        step on whichever named browser this param currently is. Handles
        BOTH the 3-button and 1-button branches via the same
        branch-aware helpers the rest of the suite uses."""
        browser_name = request.node.callspec.params["named_browser_page"]
        page = named_browser_page
        open_chat_widget(page)
        branch = resolve_goal_or_balance_step(page)
        assert branch in ("goal_selection", "single_choice"), (
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
        fill_name_step(page, DATA["first_name"], DATA["last_name"])
        fill_email_step(page, DATA["email"])
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