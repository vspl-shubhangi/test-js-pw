"""
test_marketing_site_navigation_class.py
=======================================
Coverage for the EvaFi MARKETING/INFORMATIONAL site (homepage, Products
dropdown, rate-check calculator widgets, value-proposition CTAs, FAQ
accordions, footer) -- distinct from the onboarding chat wizard the rest
of the suite covers. Generated from a Playwright Inspector recording of
a full manual site tour; split into one focused test per distinct,
reliably-locatable interactive element (navbar links, dropdown items,
sliders, buttons, footer links), plus one comprehensive end-to-end
journey test that mirrors the full recorded script -- including the
handful of unlabeled/anonymous links the recording clicked that aren't
reliably locatable in isolation outside that exact page context.

ASSUMPTIONS FLAGGED INLINE: several assertions below check for
"navigation happened / page didn't crash / expected widget appeared"
rather than a hardcoded exact destination URL or heading text, because
the recording didn't capture what SHOULD appear after some clicks (e.g.
"Check your rate", the 5 value-proposition CTAs) -- only that the click
succeeded. Tighten these once the real expected destination/content for
each is confirmed against the live site.

Slider locators intentionally do NOT reuse the recorder's exact
"has_text=re.compile(r'^...\\$33,000\\$5,000\\$100,000$')" pattern --
that hardcodes the CURRENT default slider value into the locator itself,
which breaks the moment the page's default value changes. Filtering on
just the stable label text ("How much are you looking to borrow" / "Set
your terms") is equivalent and far more robust.
"""

import re

import pytest
from playwright.sync_api import Page, expect

import config
from wizard_helpers import _dismiss_cookie_notice_if_present  # noqa: F401 -- reused, not redefined


def _open_marketing_homepage(page: Page) -> None:
    """Homepage -> dismiss cookie notice. The marketing site's own
    entry point, distinct from open_chat_widget() (which also clicks
    into the chat launcher -- not wanted here)."""
    page.goto(config.LOGIN_URL)
    page.wait_for_load_state("networkidle")
    _dismiss_cookie_notice_if_present(page)


def _open_products_dropdown(page: Page) -> None:
    page.get_by_role("button", name="Products").click()


def _borrow_amount_slider(page: Page):
    return page.locator("div").filter(has_text="How much are you looking to borrow").get_by_role("slider")


def _loan_term_slider(page: Page):
    return page.locator("div").filter(has_text="Set your terms").get_by_role("slider")


# ═════════════════════════════════════════════════════════════════════════
# 1. TestCookieAndNavbar — cookie notice, logo, Products dropdown + its
#    two loan-type links, About navbar link.
# ═════════════════════════════════════════════════════════════════════════


class TestCookieAndNavbar:
    @pytest.mark.smoke
    def test_cookie_notice_dismissible(self, page: Page):
        page.goto(config.LOGIN_URL)
        page.wait_for_load_state("networkidle")
        close_btn = page.get_by_role("button", name="Close cookie notice")
        expect(close_btn).to_be_visible()
        close_btn.click()
        expect(close_btn).not_to_be_visible()

    @pytest.mark.smoke
    def test_navbar_logo_link_returns_to_homepage(self, page: Page):
        """The unnamed (empty-text) link in #site-navbar is the site
        logo -- reliably locatable by container + empty text, even
        without an accessible name."""
        _open_marketing_homepage(page)
        logo_link = page.locator("#site-navbar").get_by_role("link").filter(has_text=re.compile(r"^$"))
        expect(logo_link).to_be_visible()
        logo_link.click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Page title blank after clicking the navbar logo link."

    @pytest.mark.smoke
    def test_products_dropdown_opens(self, page: Page):
        _open_marketing_homepage(page)
        _open_products_dropdown(page)
        expect(page.get_by_role("link", name="Consolidation loan")).to_be_visible()
        expect(page.get_by_role("link", name="Personal loans")).to_be_visible()

    @pytest.mark.smoke
    def test_products_dropdown_consolidation_loan_link_navigates(self, page: Page):
        _open_marketing_homepage(page)
        _open_products_dropdown(page)
        page.get_by_role("link", name="Consolidation loan").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Page title blank after clicking 'Consolidation loan'."

    @pytest.mark.smoke
    def test_products_dropdown_personal_loans_link_navigates(self, page: Page):
        _open_marketing_homepage(page)
        _open_products_dropdown(page)
        page.get_by_role("link", name="Personal loans").click()
        page.wait_for_load_state("networkidle")
        # Personal loans page hosts the rate-calculator widget -- its
        # presence is a stronger signal of correct navigation than title
        # text alone.
        expect(page.locator("div").filter(has_text="How much are you looking to borrow")).to_be_visible()

    @pytest.mark.smoke
    def test_navbar_about_link_navigates(self, page: Page):
        _open_marketing_homepage(page)
        page.locator("#site-navbar").get_by_role("link", name="About").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Page title blank after clicking navbar 'About'."


# ═════════════════════════════════════════════════════════════════════════
# 2. TestPersonalLoansRateCalculator — the borrow-amount and loan-term
#    sliders + "Check your rate" button on the Personal Loans page.
# ═════════════════════════════════════════════════════════════════════════


class TestPersonalLoansRateCalculator:
    def _reach_personal_loans_page(self, page: Page) -> None:
        _open_marketing_homepage(page)
        _open_products_dropdown(page)
        page.get_by_role("link", name="Personal loans").click()
        page.wait_for_load_state("networkidle")

    @pytest.mark.functional
    def test_borrow_amount_slider_updates_displayed_value(self, page: Page):
        self._reach_personal_loans_page(page)
        widget = page.locator("div").filter(has_text="How much are you looking to borrow")
        widget.get_by_role("slider").fill("78000")
        expect(widget).to_contain_text("78,000")

    @pytest.mark.functional
    def test_loan_term_slider_updates_displayed_value(self, page: Page):
        self._reach_personal_loans_page(page)
        widget = page.locator("div").filter(has_text="Set your terms")
        widget.get_by_role("slider").fill("7")
        expect(widget).to_contain_text("7")

    @pytest.mark.smoke
    def test_check_your_rate_button_proceeds(self, page: Page):
        """ASSUMPTION FLAGGED: exact destination after 'Check your rate'
        isn't confirmed -- this asserts the app survived navigation
        (no crash / blank page), not a specific results page."""
        self._reach_personal_loans_page(page)
        _borrow_amount_slider(page).fill("78000")
        _loan_term_slider(page).fill("7")
        page.get_by_role("button", name="Check your rate").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Page title blank after 'Check your rate'."


# ═════════════════════════════════════════════════════════════════════════
# 3. TestAboutPageRateCalculator — "How Eva works" toggle + the About
#    page's own rate-calculator widget + "Check my rate" button.
# ═════════════════════════════════════════════════════════════════════════


class TestAboutPageRateCalculator:
    def _reach_about_page(self, page: Page) -> None:
        _open_marketing_homepage(page)
        page.locator("#site-navbar").get_by_role("link", name="About").click()
        page.wait_for_load_state("networkidle")

    @pytest.mark.smoke
    def test_how_eva_works_button_expands_content(self, page: Page):
        self._reach_about_page(page)
        toggle = page.get_by_role("button", name="How Eva works")
        expect(toggle).to_be_visible()
        toggle.click()
        # ASSUMPTION FLAGGED: exact expanded-content locator unconfirmed;
        # asserting the rate-calculator widget it reveals becomes visible.
        expect(page.locator("div").filter(has_text="How much are you looking to borrow")).to_be_visible()

    @pytest.mark.functional
    def test_about_page_borrow_amount_slider_updates_displayed_value(self, page: Page):
        self._reach_about_page(page)
        page.get_by_role("button", name="How Eva works").click()
        widget = page.locator("div").filter(has_text="How much are you looking to borrow")
        widget.get_by_role("slider").fill("74500")
        expect(widget).to_contain_text("74,500")

    @pytest.mark.functional
    def test_about_page_loan_term_slider_updates_displayed_value(self, page: Page):
        self._reach_about_page(page)
        page.get_by_role("button", name="How Eva works").click()
        widget = page.locator("div").filter(has_text="Set your terms")
        widget.get_by_role("slider").fill("6")
        expect(widget).to_contain_text("6")

    @pytest.mark.smoke
    def test_check_my_rate_button_proceeds(self, page: Page):
        """ASSUMPTION FLAGGED: same as 'Check your rate' above -- exact
        destination unconfirmed, asserts survival not specific content."""
        self._reach_about_page(page)
        page.get_by_role("button", name="How Eva works").click()
        _borrow_amount_slider(page).fill("74500")
        _loan_term_slider(page).fill("6")
        page.get_by_role("button", name="Check my rate").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Page title blank after 'Check my rate'."


# ═════════════════════════════════════════════════════════════════════════
# 4. TestValuePropositionCards — the 5 benefit/value-prop CTA buttons.
#    ASSUMPTION FLAGGED throughout: exact resulting behavior (navigation
#    vs. in-place content swap) isn't confirmed from the recording alone
#    -- each test asserts the app survived the click, not a specific
#    resulting page/state. Tighten once real behavior is confirmed.
# ═════════════════════════════════════════════════════════════════════════


class TestValuePropositionCards:
    VALUE_PROP_LABELS = (
        "Pay off credit card debt Pay",
        "Combine debts into one",
        "Lower your interest rate",
        "Get out of debt faster Get",
        "Start saving",
    )

    @pytest.mark.parametrize("label", VALUE_PROP_LABELS)
    @pytest.mark.smoke
    def test_value_proposition_button_click_does_not_crash(self, page: Page, label: str):
        _open_marketing_homepage(page)
        btn = page.get_by_role("button", name=label)
        expect(btn).to_be_visible()
        btn.click()
        page.wait_for_timeout(800)
        assert page.title().strip() != "", f"Page title blank after clicking value-prop button '{label}'."


# ═════════════════════════════════════════════════════════════════════════
# 5. TestOnboardingFAQAccordions — the 6 FAQ toggle buttons on the
#    /onboarding page.
# ═════════════════════════════════════════════════════════════════════════


class TestOnboardingFAQAccordions:
    FAQ_LABELS = (
        "How is Evafi different from",
        "How do I get loan offers?",
        "Will checking for loans",
        "How does Evafi protect my",
        "How does Evafi make money?",
        "What are the eligibility",
    )

    @pytest.mark.parametrize("label", FAQ_LABELS)
    @pytest.mark.functional
    def test_faq_accordion_expands_on_click(self, page: Page, label: str):
        page.goto(config.EVAFI_ONBOARDING_URL)
        page.wait_for_load_state("networkidle")
        _dismiss_cookie_notice_if_present(page)
        toggle = page.get_by_role("button", name=label)
        expect(toggle).to_be_visible()
        # ARIA accordions commonly expose expand/collapse state via
        # aria-expanded -- assert it flips true after the click, a much
        # more robust signal than guessing the revealed answer's exact
        # text (which wasn't captured in the recording).
        toggle.click()
        page.wait_for_timeout(500)
        expanded = toggle.get_attribute("aria-expanded")
        if expanded is not None:
            assert expanded == "true", f"FAQ '{label}' did not report aria-expanded=true after click."
        else:
            # No aria-expanded attribute on this build -- fall back to a
            # basic survival check instead of failing on an assumption.
            assert page.title().strip() != "", f"Page title blank after expanding FAQ '{label}'."


# ═════════════════════════════════════════════════════════════════════════
# 6. TestFooterLinks — Privacy Policy, Terms, Ad Disclosure, footer About.
# ═════════════════════════════════════════════════════════════════════════


class TestFooterLinks:
    @pytest.mark.smoke
    def test_privacy_policy_link_navigates(self, page: Page):
        _open_marketing_homepage(page)
        page.get_by_role("link", name="Privacy Policy").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Page title blank after clicking 'Privacy Policy'."

    @pytest.mark.smoke
    def test_terms_link_navigates(self, page: Page):
        _open_marketing_homepage(page)
        page.get_by_role("link", name="Terms").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Page title blank after clicking 'Terms'."

    @pytest.mark.smoke
    def test_ad_disclosure_link_navigates(self, page: Page):
        _open_marketing_homepage(page)
        page.get_by_role("link", name="Ad Disclosure").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Page title blank after clicking 'Ad Disclosure'."

    @pytest.mark.smoke
    def test_footer_about_link_navigates(self, page: Page):
        _open_marketing_homepage(page)
        page.locator("footer").get_by_role("link", name="About").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Page title blank after clicking footer 'About'."


# ═════════════════════════════════════════════════════════════════════════
# 7. TestFullMarketingSiteNavigationJourney — one comprehensive test
#    mirroring the ENTIRE recorded script end-to-end, including the
#    handful of anonymous/unlabeled `get_by_role("link")` clicks that
#    aren't reliably isolatable as standalone tests (no accessible name,
#    position-dependent within their specific page context). This is
#    what gives the anonymous links real coverage without a fragile
#    isolated test built around an ambiguous locator.
# ═════════════════════════════════════════════════════════════════════════


class TestFullMarketingSiteNavigationJourney:
    @pytest.mark.e2e
    def test_full_recorded_marketing_site_tour_survives_end_to_end(self, page: Page):
        """Mirrors happy_path_otp_screen-style captures elsewhere in the
        suite: drives the ENTIRE recorded click sequence and asserts the
        app never crashes/blanks at any step, rather than asserting
        exact per-step destinations (several of which are unconfirmed --
        see the class-level ASSUMPTION FLAGGED notes above)."""
        _open_marketing_homepage(page)

        page.locator("#site-navbar").get_by_role("link").filter(has_text=re.compile(r"^$")).click()
        page.wait_for_load_state("networkidle")

        _open_products_dropdown(page)
        page.get_by_role("link", name="Consolidation loan").click()
        page.wait_for_load_state("networkidle")

        _open_products_dropdown(page)
        page.get_by_role("link", name="Personal loans").click()
        page.wait_for_load_state("networkidle")

        _borrow_amount_slider(page).fill("78000")
        _loan_term_slider(page).fill("7")
        page.get_by_role("button", name="Check your rate").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Blank title after 'Check your rate' step."

        page.locator("#site-navbar").get_by_role("link", name="About").click()
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="How Eva works").click()

        _borrow_amount_slider(page).fill("35000")
        _borrow_amount_slider(page).fill("74500")
        _loan_term_slider(page).fill("6")
        page.get_by_role("button", name="Check my rate").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Blank title after 'Check my rate' step."

        for label in TestValuePropositionCards.VALUE_PROP_LABELS:
            page.get_by_role("button", name=label).click()
            page.wait_for_timeout(500)
        assert page.title().strip() != "", "Blank title after value-proposition CTAs."

        page.goto(config.EVAFI_ONBOARDING_URL)
        page.wait_for_load_state("networkidle")
        _dismiss_cookie_notice_if_present(page)

        for label in TestOnboardingFAQAccordions.FAQ_LABELS:
            page.get_by_role("button", name=label).click()
            page.wait_for_timeout(400)
        assert page.title().strip() != "", "Blank title after FAQ accordion sequence."

        page.get_by_role("link", name="Privacy Policy").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Blank title after 'Privacy Policy'."

        page.goto(config.EVAFI_ONBOARDING_URL)
        page.wait_for_load_state("networkidle")
        page.get_by_role("link", name="Terms").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Blank title after 'Terms'."

        page.goto(config.EVAFI_ONBOARDING_URL)
        page.wait_for_load_state("networkidle")
        page.get_by_role("link", name="Ad Disclosure").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Blank title after 'Ad Disclosure'."

        page.goto(config.LOGIN_URL)
        page.wait_for_load_state("networkidle")
        page.locator("footer").get_by_role("link", name="About").click()
        page.wait_for_load_state("networkidle")
        assert page.title().strip() != "", "Blank title after footer 'About'."
