"""
test_cross_device_class.py
==========================
TestCrossDevice — split out of the original monolithic test file so each test
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


class TestCrossDevice:
    @pytest.mark.cross_device
    def test_launcher_and_branch_resolve_on_device(self, device_page: Page):
        open_chat_widget(device_page)
        branch = resolve_goal_or_balance_step(device_page)
        assert branch in ("pick_one_of_four", "pick_three_of_eight")
        advance_through_intro_slides(device_page, branch)
        expect(device_page.get_by_role("button", name="Continue")).to_be_visible()

    @pytest.mark.cross_device
    def test_name_step_fillable_on_device(self, device_page: Page):
        """Unique first legal name every run (per instruction) -- generate
        it once, fill it, then assert against that SAME generated value
        (not a second independent call, which would produce a different
        random string and make the equality assertion meaningless)."""
        drive_to_name_step(device_page)
        first_name_value = FIXED_VALID_FIRST_NAME
        first = device_page.get_by_role("textbox").first
        first.fill(first_name_value)
        expect(first).to_have_value(first_name_value)

    @pytest.mark.cross_device
    def test_phone_field_visible_and_usable_on_device(self, device_page: Page):
        drive_to_phone_step(device_page)
        phone_field = device_page.get_by_role("textbox", name="(000) 000-")
        expect(phone_field).to_be_visible()
        phone_field.fill(FIXED_VALID_PHONE)
        expect(phone_field).to_have_value(FIXED_VALID_PHONE)


# ═════════════════════════════════════════════════════════════════════════
# 5. TestRegression — field-by-field negative-input matrix, executed in
#    navigation-sequence order: first name -> last name -> email -> phone.
# ═════════════════════════════════════════════════════════════════════════