"""Tests for pylint hass_enforce_config_entry_unique_id_no_ip plugin."""

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
import pytest

from . import assert_no_messages


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        unique_id = format_mac(data["mac"])
        """,
            "homeassistant.components.test.config_flow",
            id="mac_address",
        ),
        pytest.param(
            """
        unique_id = device_info["serial_number"]
        """,
            "homeassistant.components.test.config_flow",
            id="serial_number",
        ),
        pytest.param(
            """
        await self.async_set_unique_id(device.unique_id)
        """,
            "homeassistant.components.test.config_flow",
            id="device_unique_id",
        ),
        pytest.param(
            """
        unique_id = data[CONF_HOST]
        """,
            "homeassistant.components.test.config_flow",
            id="assign_not_checked",
        ),
        pytest.param(
            """
        await self.async_set_unique_id(device.serial)
        """,
            "homeassistant.components.test.config_flow",
            id="async_set_unique_id_safe_value",
        ),
        pytest.param(
            """
        await self.async_set_unique_id(data[CONF_HOST])
        """,
            "homeassistant.components.test.sensor",
            id="async_set_unique_id_not_config_flow",
        ),
    ],
)
def test_enforce_unique_id_no_ip(
    linter: UnittestLinter,
    enforce_config_entry_unique_id_no_ip_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_config_entry_unique_id_no_ip_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        await self.async_set_unique_id(entry.data[CONF_HOST])
        """,
            "homeassistant.components.test.config_flow",
            id="async_set_conf_host",
        ),
        pytest.param(
            """
        await self.async_set_unique_id(data[CONF_IP_ADDRESS])
        """,
            "homeassistant.components.test.config_flow",
            id="async_set_conf_ip",
        ),
        pytest.param(
            """
        await self.async_set_unique_id(user_input["host"])
        """,
            "homeassistant.components.test.config_flow",
            id="async_set_string_host",
        ),
        pytest.param(
            """
        await self.async_set_unique_id(unique_id=entry.data[CONF_HOST])
        """,
            "homeassistant.components.test.config_flow",
            id="async_set_conf_host_keyword",
        ),
        pytest.param(
            """
        await self.async_set_unique_id(
            unique_id=data[CONF_IP_ADDRESS], raise_on_progress=False
        )
        """,
            "homeassistant.components.test.config_flow",
            id="async_set_conf_ip_keyword_raise_on_progress_false",
        ),
    ],
)
def test_enforce_unique_id_no_ip_bad_call(
    linter: UnittestLinter,
    enforce_config_entry_unique_id_no_ip_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Bad async_set_unique_id call test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_config_entry_unique_id_no_ip_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-unique-id-ip-based"


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
async def async_step_user(self, user_input=None):
    unique_id = data[CONF_HOST]
    await self.async_set_unique_id(unique_id)
        """,
            "homeassistant.components.test.config_flow",
            id="variable_from_subscript",
        ),
        pytest.param(
            """
async def async_step_user(self, user_input=None):
    unique_id = f"prefix_{data[CONF_HOST]}"
    await self.async_set_unique_id(unique_id)
        """,
            "homeassistant.components.test.config_flow",
            id="variable_from_fstring",
        ),
        pytest.param(
            """
async def async_step_user(self, user_input=None):
    if discovered:
        unique_id = device.mac
    else:
        unique_id = data[CONF_HOST]
    await self.async_set_unique_id(unique_id)
        """,
            "homeassistant.components.test.config_flow",
            id="variable_from_conditional",
        ),
        pytest.param(
            """
async def async_step_user(self, user_input=None):
    unique_id = data.get(CONF_HOST)
    await self.async_set_unique_id(unique_id)
        """,
            "homeassistant.components.test.config_flow",
            id="variable_from_dict_get",
        ),
    ],
)
def test_enforce_unique_id_no_ip_bad_call_variable(
    linter: UnittestLinter,
    enforce_config_entry_unique_id_no_ip_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Bad async_set_unique_id call test cases."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_config_entry_unique_id_no_ip_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-unique-id-ip-based"
