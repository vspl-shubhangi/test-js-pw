"""
conftest.py
===========
Shared Playwright fixtures for the Evafi onboarding-wizard test suite.

MUST live at the PROJECT ROOT (sibling of config.py, wizard_helpers.py,
report_to_db.py, pytest.ini) -- NOT inside tests/. Placing it inside
tests/ breaks `import config` in every test file under the bare `pytest`
console-script invocation: pytest's default "prepend" import mode adds
a conftest.py's own directory to sys.path, and the whole suite relies on
that directory being the project root (where config.py/wizard_helpers.py
actually live), not the tests/ subfolder.

Fixtures provided:
    page            -> function-scoped Page, supplied by the pytest-playwright
                        plugin itself (installed via requirements.txt). No
                        redefinition needed here; it uses --browser / headed
                        settings from pytest.ini / CLI flags.
    browser_engine  -> session-scoped string identifying which Playwright
                        engine is active ("chromium" | "firefox" | "webkit"),
                        read from the --browser CLI flag pytest-playwright
                        already exposes. Useful for logging / conditional
                        skips inside tests.
    device_page     -> function-scoped Page, parametrized across
                        desktop / tablet / mobile viewports+UA so any test
                        that takes device_page runs once per device
                        automatically (see TestCrossDevice in the test file).

Run configuration (headless/headed, browser choice, slow-mo, etc.) is driven
by pytest.ini and CLI flags -- see README.md for the full flag list.
"""

import os
from typing import Generator

import pytest
from playwright.sync_api import Browser, Page


# ─────────────────────────────────────────────────────────────────────────
# browser_engine — exposes which engine pytest-playwright launched
# ─────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def browser_engine(pytestconfig) -> str:
    """Name of the Playwright engine in use for this run.

    Driven by the standard pytest-playwright --browser CLI option
    (defaults to chromium). Example:
        pytest --browser firefox
        pytest --browser webkit
    """
    return pytestconfig.getoption("--browser") or "chromium"


# ─────────────────────────────────────────────────────────────────────────
# device_page — parametrized Page fixture for desktop / tablet / mobile
# ─────────────────────────────────────────────────────────────────────────

DEVICE_PROFILES = {
    "desktop": {
        "viewport": {"width": 1440, "height": 900},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "is_mobile": False,
        "has_touch": False,
    },
    "tablet": {
        "viewport": {"width": 810, "height": 1080},
        "user_agent": (
            "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
        ),
        "is_mobile": True,
        "has_touch": True,
    },
    "mobile": {
        "viewport": {"width": 390, "height": 844},
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
            "Mobile/15E148 Safari/604.1"
        ),
        "is_mobile": True,
        "has_touch": True,
    },
}


@pytest.fixture(params=list(DEVICE_PROFILES.keys()), ids=list(DEVICE_PROFILES.keys()))
def device_page(request, browser: Browser) -> Generator[Page, None, None]:
    """Yields a Page inside a fresh BrowserContext emulating the given
    device profile. Any test that declares device_page: Page as a
    parameter is automatically run once per device (desktop/tablet/mobile).

    Relies on the session-scoped browser fixture from pytest-playwright.
    """
    profile = DEVICE_PROFILES[request.param]
    context = browser.new_context(
        viewport=profile["viewport"],
        user_agent=profile["user_agent"],
        is_mobile=profile["is_mobile"],
        has_touch=profile["has_touch"],
    )
    page = context.new_page()
    yield page
    context.close()


# ─────────────────────────────────────────────────────────────────────────
# Force real Google Chrome by default (not Playwright's bundled Chromium).
# pytest.ini already passes --browser-channel chrome, but this fixture
# guarantees it even if someone runs pytest with a different/no ini file,
# or overrides --browser on the CLI without also passing --browser-channel.
#
# Requires Chrome to be registered with Playwright once via:
#     playwright install chrome
# ─────────────────────────────────────────────────────────────────────────


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
def named_browser_page(request, playwright) -> Generator[Page, None, None]:
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


# ═════════════════════════════════════════════════════════════════════════
# FULL DEVICE × BROWSER MATRIX — 5 device profiles × 4 browsers = 20
# combinations, each running every test in the 6 content classes below
# (TestFunctional, TestSmokeAdvanced, TestDataRetention, TestSecurity,
# TestKeyboardInteraction, TestHappyPath).
#
# Rather than hand-writing 20 near-duplicate copies of each class (which
# would be unmaintainable and error-prone), a SINGLE parametrized fixture
# (`matrix_page`) covers the full cross product. Any test that takes
# `matrix_page` as a parameter is automatically run once per device ×
# browser combo — this is the standard pytest pattern for exactly this
# requirement and is what conftest.py's own `device_page` fixture already
# does on a smaller scale.
#
#   Devices : smartphone_android (Pixel 5) | smartphone_iphone (iPhone 13)
#             | tablet_android (Galaxy Tab S4) | tablet_iphone (iPad gen 7)
#             | desktop (1440x900, no device emulation)
#   Browsers: chrome | firefox | brave | msedge
#
# Every drive_to_* helper used inside these classes already routes
# through open_chat_widget() -> resolve_goal_or_balance_step() ->
# advance_through_intro_slides(), so the random 3-option / 1-option
# screen is handled correctly on every single one of these 20 combos
# with zero extra code in the test bodies themselves.
# ═════════════════════════════════════════════════════════════════════════

MOBILE_DEVICE_DESCRIPTORS = {
    "smartphone_android": "Pixel 5",
    "smartphone_iphone": "iPhone 13",
    "tablet_android": "Galaxy Tab S4",
    "tablet_iphone": "iPad (gen 7)",
}
DEVICE_NAMES = [*MOBILE_DEVICE_DESCRIPTORS.keys(), "desktop"]

# Only the 4 browsers actually requested for the full matrix (plain
# "chromium" stays exclusive to the smaller named_browser_page fixture
# above / TestCrossBrowserMatrix).
CROSS_BROWSER_ENGINES = {
    name: cfg for name, cfg in NAMED_BROWSER_LAUNCH_CONFIG.items() if name != "chromium"
}

MATRIX_PARAMS = [(d, b) for d in DEVICE_NAMES for b in CROSS_BROWSER_ENGINES]
MATRIX_IDS = [f"{d}-{b}" for d, b in MATRIX_PARAMS]


@pytest.fixture(params=MATRIX_PARAMS, ids=MATRIX_IDS)
def matrix_page(request, playwright) -> Generator[Page, None, None]:
    """Function-scoped Page for ONE (device, browser) combination out of
    the full 20-entry matrix. See module-level comment block above for
    the device/browser lists and rationale."""
    device_name, browser_name = request.param
    browser_cfg = CROSS_BROWSER_ENGINES[browser_name]
    engine = getattr(playwright, browser_cfg["engine"])

    launch_kwargs = {"headless": False}
    if browser_cfg.get("channel"):
        launch_kwargs["channel"] = browser_cfg["channel"]
    if browser_cfg.get("needs_brave_path"):
        brave_path = _resolve_brave_executable()
        if not brave_path:
            pytest.skip(
                "Brave executable not found locally. Install Brave, or "
                "set BRAVE_EXECUTABLE_PATH to its binary path, to "
                "include Brave in the full device x browser matrix."
            )
        launch_kwargs["executable_path"] = brave_path

    try:
        browser = engine.launch(**launch_kwargs)
    except Exception as exc:
        pytest.skip(f"Could not launch '{browser_name}': {exc}")
        return

    if device_name == "desktop":
        context_kwargs = {"viewport": {"width": 1440, "height": 900}}
    else:
        descriptor = dict(playwright.devices[MOBILE_DEVICE_DESCRIPTORS[device_name]])
        if browser_cfg["engine"] != "chromium":
            # Playwright only supports the "is_mobile" context option on
            # Chromium-family engines (chrome/brave/msedge here) -- it
            # raises on Firefox, so strip it for that combination while
            # keeping viewport/user_agent/touch emulation intact.
            descriptor.pop("is_mobile", None)
        context_kwargs = descriptor

    context = browser.new_context(**context_kwargs)
    page = context.new_page()
    yield page
    context.close()
    browser.close()


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args, pytestconfig):
    launch_args = {**browser_type_launch_args}
    # Respect an explicit --browser-channel CLI override if one was given;
    # otherwise default to "chrome".
    channel = pytestconfig.getoption("browser_channel", default=None) or "chrome"
    launch_args["channel"] = channel
    return launch_args


# ─────────────────────────────────────────────────────────────────────────
# Screenshot-on-failure hook — saves a screenshot for any failed test that
# used a page or device_page fixture, into reports/screenshots/.
# ─────────────────────────────────────────────────────────────────────────

import os
from datetime import datetime


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        page_fixture = item.funcargs.get("page") or item.funcargs.get("device_page")
        if page_fixture is not None:
            screenshots_dir = os.path.join(os.path.dirname(__file__), "reports", "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = item.name.replace("/", "").replace("::", "")
            screenshot_path = os.path.join(screenshots_dir, f"{safe_name}_{timestamp}.png")
            try:
                page_fixture.screenshot(path=screenshot_path)
                print(f"\nScreenshot saved: {screenshot_path}")
            except Exception as exc:  # pragma: no cover
                print(f"\nCould not capture screenshot: {exc}")


# ─────────────────────────────────────────────────────────────────────────
# Apache Superset pipeline — auto-load report.html into the SQL database
# Superset reads from, right after each pytest run finishes.
#
# pytest_unconfigure fires very late in the process (after pytest-html has
# already written report.html during its own pytest_sessionfinish hook),
# which is what guarantees the file actually exists on disk by the time
# we try to parse it here. Using pytest_sessionfinish directly risks a
# race against pytest-html's own hook depending on hook registration
# order, which is why this uses pytest_unconfigure instead.
#
# This step is intentionally best-effort: a broken/missing report.html
# (e.g. a run that crashed before pytest-html could write anything) will
# print a warning here but will NEVER fail the test run itself.
# ─────────────────────────────────────────────────────────────────────────

def pytest_unconfigure(config):
    # With pytest-xdist parallel execution (-n 4 etc.), pytest_unconfigure
    # fires on EVERY worker process too, not just the main/master one.
    # Only the master process ever sees the final, fully-aggregated
    # report.html (pytest-html writes it from the master after all
    # workers finish) -- workers have a `workerinput` attribute on their
    # config that the master doesn't, so this skips the ETL entirely on
    # workers rather than have them all redundantly no-op against a
    # report.html that isn't ready yet from their point of view.
    if hasattr(config, "workerinput"):
        return

    # conftest.py now lives at the PROJECT ROOT itself (sibling of
    # config.py/report_to_db.py/pytest.ini) -- not inside tests/ -- so
    # its own directory IS the project root. See the module docstring
    # note below for why root placement is required in the first place.
    project_root = os.path.dirname(os.path.abspath(__file__))
    report_path = os.path.join(project_root, "reports", "report.html")

    # Set EVAFI_DB_URL in your environment / .env file to point at your
    # own Postgres instance -- e.g.
    #   EVAFI_DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/evafi_results
    # Falls back to report_to_db.py's own default (also Postgres) if unset.
    # Superset cannot connect to SQLite databases at all (it hardcodes a
    # security policy against the sqlite dialect), so Postgres is the
    # only backend that actually works once you get to the Superset step.
    db_url = os.getenv("EVAFI_DB_URL")

    if not os.path.exists(report_path):
        return  # nothing to load yet (e.g. --collect-only runs, or a crashed session)

    try:
        import sys
        sys.path.insert(0, project_root)
        from report_to_db import load_report_into_db, DEFAULT_DB_URL

        effective_db_url = db_url or DEFAULT_DB_URL
        run_id, total, passed, failed, skipped, errored, pass_rate = load_report_into_db(
            report_path, effective_db_url
        )
        target_label = effective_db_url.split("@")[-1] if "@" in effective_db_url else effective_db_url
        print(
            f"\n[Superset pipeline] Loaded run {run_id} into {target_label}: "
            f"{total} tests -> {passed} passed, {failed} failed, {skipped} skipped "
            f"({pass_rate}% pass rate). Refresh the Superset dashboard to see it."
        )
    except Exception as exc:  # pragma: no cover -- never let this break a test run
        print(f"\n[Superset pipeline] Could not auto-load report.html into the DB: {exc}")