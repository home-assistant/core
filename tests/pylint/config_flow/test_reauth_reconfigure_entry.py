"""Tests for the reauth/reconfigure config entry helper checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.config_flow.reauth_reconfigure_entry import (
    LOOKUP_METHODS,
    HassEnforceReauthReconfigureEntryHelperChecker,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

_MODULE = "homeassistant.components.test_int.config_flow"


@pytest.fixture(name="checker")
def checker_fixture(
    linter: UnittestLinter,
) -> HassEnforceReauthReconfigureEntryHelperChecker:
    """Fixture to provide a reauth/reconfigure entry helper checker."""
    return HassEnforceReauthReconfigureEntryHelperChecker(linter)


@pytest.mark.parametrize(
    ("code", "helper"),
    [
        pytest.param(
            """
class TestConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_reauth(self, entry_data):
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()
""",
            "_get_reauth_entry",
            id="reauth_subscript",
        ),
        pytest.param(
            """
class TestConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_reconfigure(self, user_input=None):
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return self.async_show_form(step_id="reconfigure")
""",
            "_get_reconfigure_entry",
            id="reconfigure_subscript",
        ),
        pytest.param(
            """
class TestConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_reauth_confirm(self, user_input=None):
        entry = self.hass.config_entries.async_get_entry(
            self.context.get("entry_id")
        )
        return self.async_show_form(step_id="reauth_confirm")
""",
            "_get_reauth_entry",
            id="reauth_confirm_context_get",
        ),
        pytest.param(
            """
class TestConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_reconfigure(self, user_input=None):
        entry = self.hass.config_entries.async_get_known_entry(
            self.context["entry_id"]
        )
        return self.async_show_form(step_id="reconfigure")
""",
            "_get_reconfigure_entry",
            id="async_get_known_entry",
        ),
        pytest.param(
            """
class TestConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_reauth(self, entry_data):
        entry_id = self.context["entry_id"]
        entry = self.hass.config_entries.async_get_entry(entry_id)
        return await self.async_step_reauth_confirm()
""",
            "_get_reauth_entry",
            id="aliased_variable",
        ),
        pytest.param(
            """
class TestConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_reauth(self, entry_data):
        self._entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()
""",
            "_get_reauth_entry",
            id="reauth_assign_to_attribute",
        ),
    ],
)
def test_bad(
    linter: UnittestLinter,
    checker: HassEnforceReauthReconfigureEntryHelperChecker,
    code: str,
    helper: str,
) -> None:
    """Test manual config entry lookups in reauth/reconfigure steps are flagged."""
    root = astroid.parse(code, _MODULE)
    call = next(
        call
        for call in root.nodes_of_class(nodes.Call)
        if isinstance(call.func, nodes.Attribute)
        and call.func.attrname in LOOKUP_METHODS
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-use-reauth-reconfigure-entry-helper",
            node=call,
            args=(helper,),
            line=call.lineno,
            col_offset=call.col_offset,
            end_line=call.end_lineno,
            end_col_offset=call.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
class TestConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return self.async_show_form(step_id="user")
""",
            id="user_step",
        ),
        pytest.param(
            """
class TestConfigFlow(ConfigFlow, domain=DOMAIN):
    def _get_entry(self):
        return self.hass.config_entries.async_get_entry(self.context["entry_id"])
""",
            id="private_helper",
        ),
        pytest.param(
            """
class TestConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_reauth(self, entry_data):
        for flow in self._async_in_progress():
            entry = self.hass.config_entries.async_get_entry(
                flow["context"]["entry_id"]
            )
        return await self.async_step_reauth_confirm()
""",
            id="other_flow_context",
        ),
        pytest.param(
            """
class TestOptionsFlow(OptionsFlow):
    async def async_step_reconfigure(self, user_input=None):
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return self.async_show_form(step_id="reconfigure")
""",
            id="options_flow",
        ),
        pytest.param(
            """
class TestSubentryFlow(ConfigSubentryFlow):
    async def async_step_reconfigure(self, user_input=None):
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return self.async_show_form(step_id="reconfigure")
""",
            id="config_subentry_flow",
        ),
        pytest.param(
            """
class TestConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_reauth(self, entry_data):
        entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        return self.async_show_form(step_id="reconfigure")
""",
            id="uses_helper",
        ),
        pytest.param(
            """
class TestConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_reauth(self, entry_data):
        entry = self.hass.config_entries.async_get_entry(entry_data["entry_id"])
        return await self.async_step_reauth_confirm()
""",
            id="other_entry_id_source",
        ),
        pytest.param(
            """
async def async_step_reauth(self, entry_data):
    return self.hass.config_entries.async_get_entry(self.context["entry_id"])
""",
            id="not_in_class",
        ),
    ],
)
def test_good(
    linter: UnittestLinter,
    checker: HassEnforceReauthReconfigureEntryHelperChecker,
    code: str,
) -> None:
    """Test code that must not be flagged."""
    root = astroid.parse(code, _MODULE)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root)
