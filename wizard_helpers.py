"""
wizard_helpers.py
==================
Shared, IMPORT-ONLY helper functions for the Evafi onboarding-wizard test
suite. No fixtures live here (those are in conftest.py, where pytest can
auto-discover them) — this module is pure functions + shared constants,
imported explicitly by every tests/test_*_class.py file:

    from wizard_helpers import *

__all__ below controls exactly what that star-import brings in, so IDEs
and linters can still resolve names cleanly.

Every drive_to_*() helper routes through open_chat_widget() ->
resolve_goal_or_balance_step() -> advance_through_intro_slides(), which is
what makes the random intro-screen branch transparent to every test file.
"""

import random

import config
from playwright.sync_api import Page

DATA = config.EVAFI_TEST_DATA
INVALID_CASES = list(config.EVAFI_INVALID_INPUTS.items())
INVALID_IDS = list(config.EVAFI_INVALID_INPUTS.keys())

# ── Fixed values for EVERY "valid input" test (happy path, end-to-end,
# and any other test that needs a value the real backend will accept as
# genuinely valid) — per explicit instruction: name, email, phone, and
# DOB are ALL fixed to the same values on every run, no per-run
# uniqueness anywhere. ───────────────────────────────────────────────
FIXED_VALID_EMAIL = "ankush@coreerp.com"
FIXED_VALID_PHONE = "9096392995"
FIXED_VALID_FIRST_NAME = "Ankush"
FIXED_VALID_LAST_NAME = "Hujare"
FIXED_VALID_DOB_MONTH = "11"
FIXED_VALID_DOB_DAY = "26"
FIXED_VALID_DOB_YEAR = "2001"  # DOB = 11/26/2001 (MM/DD/YYYY)

# The 8-button branch: exactly 3 of these 8 must be clicked, randomly,
# a DIFFERENT 3 each run (confirmed against happy_path_otp_screen.py —
# all 8 labels are directly visible in that capture).
GOAL_SELECTION_LABELS_8 = (
    "Lower my monthly payment",
    "Pay off debt sooner",
    "Cut my interest costs",
    "Single monthly payment",
    "Build my credit health",
    "Avoid late fees & penalties",
    "Get out of debt—period",
    "Reduce financial stress",
)

# The 4-button branch: exactly 1 of these 4 must be clicked, randomly, a
# DIFFERENT 1 each run (confirmed against the updated
# happy_path_otp_screen.py capture — all 4 labels are directly visible).
GOAL_SELECTION_LABELS_4 = (
    "My balances barely go down",
    "Interest charges keep piling up",
    "The monthly payments are too much",
    "Honestly, all of the above",
)

__all__ = [
    "DATA",
    "INVALID_CASES",
    "INVALID_IDS",
    "FIXED_VALID_EMAIL",
    "FIXED_VALID_PHONE",
    "FIXED_VALID_FIRST_NAME",
    "FIXED_VALID_LAST_NAME",
    "FIXED_VALID_DOB_MONTH",
    "FIXED_VALID_DOB_DAY",
    "FIXED_VALID_DOB_YEAR",
    "GOAL_SELECTION_LABELS_8",
    "GOAL_SELECTION_LABELS_4",
    "open_chat_widget",
    "resolve_goal_or_balance_step",
    "advance_through_intro_slides",
    "drive_to_name_step",
    "fill_name_step",
    "drive_to_email_step",
    "fill_email_step",
    "drive_to_debt_amount_step",
    "select_debt_amount",
    "drive_to_dob_step",
    "fill_dob_step",
    "drive_to_phone_step",
    "fill_phone_step",
    "drive_to_otp_step",
    "fill_otp_step",
    "random_six_digit_otp",
    "drive_to_offers_step",
    "_assert_app_survived_invalid_input",
    "_assert_no_js_dialog_fires",
    "_dismiss_cookie_notice_if_present",
]


# NOTE: this module previously generated a fresh unique first/last name
# and DOB per test run (unique_legal_name() / unique_dob_mmddyyyy()).
# That functionality has been REMOVED per explicit instruction -- it was
# causing test failures. Every "valid input" test now uses the fixed
# FIXED_VALID_FIRST_NAME / FIXED_VALID_LAST_NAME / FIXED_VALID_DOB_*
# constants defined above instead (Ankush / Hujare / 11/26/2001).


def random_six_digit_otp() -> str:
    """A different 6-digit OTP string every call (e.g. '482913'), per
    the instruction that the OTP entered in happy-path/E2E tests must
    NOT be fixed to the same digits every run."""
    return f"{random.randint(0, 999999):06d}"


# ── Cookie notice / launcher / intro-advance (viewport-responsive) ─────


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

    On desktop/tablet viewports it lives inside #site-navbar. On mobile
    viewports it does not (see the three_opt_mob_view.py capture, which
    clicks an UNSCOPED `get_by_role("button", name="Chat with Eva").first`
    instead). Strategy: try the desktop-scoped locator first, fall back
    to the unscoped mobile-capture locator if it doesn't appear in time.
    """
    navbar_launcher = page.locator("#site-navbar").get_by_role("button", name="Chat with Eva")
    try:
        navbar_launcher.wait_for(state="visible", timeout=6000)
        navbar_launcher.click()
        return
    except Exception:
        pass
    page.get_by_role("button", name="Chat with Eva").first.click()


def _click_intro_advance_button(page: Page) -> None:
    """'Go forward' on desktop/tablet captures, 'Let's get started' on
    the mobile capture — same step, different copy per viewport."""
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
    across desktop/tablet/mobile."""
    page.goto(config.LOGIN_URL)
    page.wait_for_load_state("networkidle")
    _dismiss_cookie_notice_if_present(page)
    _click_chat_launcher(page)
    _dismiss_cookie_notice_if_present(page)
    _click_intro_advance_button(page)


# ── The non-deterministic branch — NOW two possible screens, each with
# a RANDOM subset selection (not a fixed one) ───────────────────────────


def resolve_goal_or_balance_step(page: Page) -> str:
    """
    Detects which of the two goal-selection screens rendered THIS run:

      - "pick_one_of_four":   4 independent buttons — exactly ONE must
        be clicked, and it must be a DIFFERENT one at random each run
        (not always the same button).
      - "pick_three_of_eight": 8 independent buttons — exactly THREE
        must be clicked, and they must be a DIFFERENT random trio each
        run (not always the same three).

    Returns which branch was taken; does NOT click anything itself —
    see advance_through_intro_slides() below for the random selection +
    click + Next/Continue navigation.
    """
    four_btn = page.get_by_role("button", name=GOAL_SELECTION_LABELS_4[0])
    try:
        four_btn.wait_for(state="visible", timeout=4000)
        return "pick_one_of_four"
    except Exception:
        pass

    eight_btn = page.get_by_role("button", name=GOAL_SELECTION_LABELS_8[0])
    eight_btn.wait_for(state="visible", timeout=6000)
    return "pick_three_of_eight"


def advance_through_intro_slides(page: Page, branch: str) -> None:
    """Performs the RANDOM selection for whichever branch resolved, then
    the Next/Continue navigation that follows it.

      - "pick_one_of_four": click ONE random label out of
        GOAL_SELECTION_LABELS_4, then 1x "Next", then "Continue".
      - "pick_three_of_eight": click THREE random distinct labels out of
        GOAL_SELECTION_LABELS_8, then 3x "Next", then "Continue".

    The Next-click count matching the number of options selected mirrors
    the pattern already confirmed for the suite's earlier 2-branch
    screen (1 pick -> 1 Next, 3 picks -> 3 Next) and lines up with the
    explicit 3x "Next" click sequence shown in happy_path_otp_screen.py
    for the 3-pick branch. Flag this assumption if the app's real
    behavior differs once you can exercise both branches directly.
    """
    if branch == "pick_one_of_four":
        chosen = [random.choice(GOAL_SELECTION_LABELS_4)]
    elif branch == "pick_three_of_eight":
        chosen = random.sample(GOAL_SELECTION_LABELS_8, 3)
    else:
        raise ValueError(f"Unknown branch: {branch!r}")

    for label in chosen:
        page.get_by_role("button", name=label).click()

    for _ in range(len(chosen)):
        page.get_by_role("button", name="Next").click()
    page.get_by_role("button", name="Continue").click()


# ── Cumulative drive_to_* helpers — each one reaches exactly one step ──


def drive_to_name_step(page: Page) -> None:
    open_chat_widget(page)
    branch = resolve_goal_or_balance_step(page)
    advance_through_intro_slides(page, branch)


def fill_name_step(page: Page, first_name: str = None, last_name: str = None, submit: bool = True) -> None:
    """first_name/last_name default to the FIXED valid values
    (FIXED_VALID_FIRST_NAME / FIXED_VALID_LAST_NAME = "Ankush"/"Hujare")
    when omitted -- every 'valid input' test uses these same fixed
    values, not a unique-per-run generated name. Pass explicit values
    (as TestSecurity/TestRegression/TestFunctional's edge-case tests
    already do) to keep deterministic payloads for those tests."""
    first_name = first_name if first_name is not None else FIXED_VALID_FIRST_NAME
    last_name = last_name if last_name is not None else FIXED_VALID_LAST_NAME
    page.get_by_role("textbox").first.fill(first_name)
    page.get_by_role("textbox").nth(1).fill(last_name)
    if submit:
        page.get_by_role("button", name="Continue").click()


def drive_to_email_step(page: Page) -> None:
    drive_to_name_step(page)
    fill_name_step(page)  # FIXED_VALID_FIRST_NAME / FIXED_VALID_LAST_NAME


def fill_email_step(page: Page, email: str = None, submit: bool = True) -> None:
    """Defaults to FIXED_VALID_EMAIL when omitted -- email is fixed for
    every valid-input test per instruction, unlike name/DOB."""
    email = email if email is not None else FIXED_VALID_EMAIL
    page.get_by_role("textbox").fill(email)
    if submit:
        page.get_by_role("button", name="Continue").click()


def drive_to_debt_amount_step(page: Page) -> None:
    drive_to_email_step(page)
    fill_email_step(page)  # FIXED_VALID_EMAIL
    # happy_path_otp_screen.py: "#here add wait of 20 sec" -- appears
    # immediately after the email-step Continue click, before the
    # second Continue that reveals the debt-amount screen.
    page.wait_for_timeout(20_000)
    page.get_by_role("button", name="Continue").click()  # 2nd Continue after email (info screen)


def select_debt_amount(page: Page, label: str) -> None:
    page.get_by_role("button", name=label).click()
    for _ in range(3):
        page.get_by_role("button", name="Continue").click()


def drive_to_dob_step(page: Page) -> None:
    drive_to_debt_amount_step(page)
    select_debt_amount(page, DATA["debt_amount"])


def fill_dob_step(page: Page, month: str = None, day: str = None, year: str = None, submit: bool = True) -> None:
    """month/day/year default to the FIXED valid DOB
    (FIXED_VALID_DOB_MONTH/DAY/YEAR = 11/26/2001) when omitted -- every
    'valid input' test uses this same fixed DOB, not a unique-per-run
    generated one. Pass explicit values (as TestFunctional's BVA tests
    already do) for deterministic boundary-value payloads."""
    if month is None or day is None or year is None:
        month, day, year = FIXED_VALID_DOB_MONTH, FIXED_VALID_DOB_DAY, FIXED_VALID_DOB_YEAR
    page.get_by_role("textbox").first.fill(month)
    page.get_by_role("textbox").nth(1).fill(day)
    page.get_by_role("textbox").nth(2).fill(year)
    if submit:
        page.get_by_role("button", name="Continue").click()


def drive_to_phone_step(page: Page) -> None:
    drive_to_dob_step(page)
    fill_dob_step(page)  # FIXED_VALID_DOB_MONTH/DAY/YEAR (11/26/2001)


def fill_phone_step(page: Page, phone: str = None, submit: bool = True) -> None:
    """Defaults to FIXED_VALID_PHONE when omitted -- phone is fixed for
    every valid-input test per instruction, unlike name/DOB."""
    phone = phone if phone is not None else FIXED_VALID_PHONE
    page.get_by_role("textbox", name="(000) 000-").fill(phone)
    if submit:
        page.get_by_role("button", name="Send code").click()
        # happy_path_otp_screen.py: "#here add wait of 30 sec" --
        # appears immediately after "Send code" is clicked.
        page.wait_for_timeout(30_000)


def drive_to_otp_step(page: Page) -> None:
    """Reaches the OTP screen. NOTE: this calls 'Send code', which
    triggers a REAL SMS in this environment."""
    drive_to_phone_step(page)
    fill_phone_step(page)  # FIXED_VALID_PHONE


def fill_otp_step(page: Page, digits: str = None) -> None:
    """digits defaults to a freshly generated random 6-digit OTP string
    each call when omitted -- per instruction that the OTP must NOT be
    fixed to the same value every run (e.g. always '123456')."""
    digits = digits if digits is not None else random_six_digit_otp()
    boxes = page.locator("div:nth-child(5) > div > div > input")
    for i, digit in enumerate(digits):
        boxes.nth(i).fill(digit)
    page.get_by_role("button", name="Continue").click()
    # happy_path_otp_screen.py: "#here add wait of 35 sec" -- appears
    # immediately after the OTP-step Continue click, before "Find offers".
    page.wait_for_timeout(35_000)


def drive_to_offers_step(page: Page) -> None:
    """Full happy-path terminus, past OTP entry: OTP Continue -> Find
    offers -> Get offer -> Connect to EvaFi Agent. This is the NEW,
    deeper happy-path flow from happy_path_otp_screen.py -- previously
    the suite stopped at the OTP screen without assuming a real code;
    this goes further because the capture shows an arbitrary 6-digit
    code proceeding successfully (staging environment does not appear
    to validate the OTP value itself)."""
    drive_to_otp_step(page)
    fill_otp_step(page)  # random 6-digit OTP, per-call
    page.get_by_role("button", name="Find offers").click()
    page.get_by_role("button", name="Get offer").click()
    page.get_by_role("button", name="Connect to EvaFi Agent").click()


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


def _assert_no_js_dialog_fires(page: Page, trigger) -> None:
    """Runs `trigger()` (a zero-arg callable) while watching for a JS
    dialog (alert/confirm/prompt). If one fires, the payload executed as
    live script/markup instead of being neutralized -- a real XSS hit."""
    dialog_fired = {"flag": False}

    def _handle_dialog(dialog):
        dialog_fired["flag"] = True
        dialog.dismiss()

    page.on("dialog", _handle_dialog)
    trigger()
    page.wait_for_timeout(1200)
    assert not dialog_fired["flag"], (
        "A JS dialog fired after submitting the payload — it executed as "
        "live script instead of being neutralized. Likely XSS."
    )