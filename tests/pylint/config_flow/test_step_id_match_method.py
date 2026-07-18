"""Tests for pylint hass_enforce_config_flow_no_polling plugin."""

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

from tests.pylint import assert_no_messages, walk_checker


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="correct_method_user",
        ),
        pytest.param(
            """
        async def async_step_reconfigure() -> FlowResult:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="correct_method_reconfigure",
        ),
        pytest.param(
            """
        async def async_step_custom() -> FlowResult:
            return self.async_show_form(
                step_id="custom",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="correct_method_custom",
        ),
        pytest.param(
            """
        async def async_common_step() -> FlowResult:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="common_step_method",
        ),
        pytest.param(
            """
        async def async_common_step() -> FlowResult:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )

        async def async_step_user() -> FlowResult:
            return await self.async_common_step()
        """,
            "homeassistant.components.test.sensor",
            id="using_common_step_from_user",
        ),
    ],
)
def test_step_id_match_method(
    linter: UnittestLinter,
    step_id_match_method_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, step_id_match_method_checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        async def async_step_user() -> FlowResult:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="incorrect_method_user",
        ),
        pytest.param(
            """
        async def async_step_reconfigure() -> FlowResult:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="incorrect_method_reconfigure",
        ),
        pytest.param(
            """
        async def async_step_custom() -> FlowResult:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                }),
            )
        """,
            "homeassistant.components.test.config_flow",
            id="incorrect_method_custom",
        ),
    ],
)
def test_step_id_match_method_bad(
    linter: UnittestLinter,
    step_id_match_method_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Bad test cases."""
    root_node = astroid.parse(code, module_name)

    walk_checker(linter, step_id_match_method_checker, root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-step_id-match-method"
