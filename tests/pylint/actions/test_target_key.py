"""Tests for the action target key checker."""

from collections.abc import Generator

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.actions.target_key import (
    TargetKeyChecker,
    clear_target_actions_cache,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

_IMPORTS = """
from homeassistant.components.light import LightService
from homeassistant.components.zwave_js.const import ZWaveJSService
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CommonServiceArgument,
    TargetKey,
)
"""


@pytest.fixture(name="target_key_checker")
def target_key_checker_fixture(
    linter: UnittestLinter,
) -> Generator[TargetKeyChecker]:
    """Fixture to provide a target key checker."""
    clear_target_actions_cache()
    yield TargetKeyChecker(linter)
    clear_target_actions_cache()


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
hass.services.async_call("light", LightService.TURN_ON, {TargetKey.ENTITY_ID: "light.kitchen"})
""",
            id="target_key",
        ),
        pytest.param(
            """
hass.services.async_call("light", LightService.TURN_ON, {"entity_id": "light.kitchen"})
""",
            id="string_literal",
        ),
        pytest.param(
            """
hass.services.async_call(
    "zwave_js",
    ZWaveJSService.SET_VALUE,
    {CommonServiceArgument.ENTITY_ID: "lock.front_door"},
)
""",
            id="real_entity_id_field",
        ),
        pytest.param(
            """
hass.services.async_call("light", "turn_on", {ATTR_ENTITY_ID: "light.kitchen"})
""",
            id="action_not_an_enum_member",
        ),
        pytest.param(
            """
hass.services.async_call("light", LightService.TURN_ON, data)
""",
            id="data_not_a_dict",
        ),
        pytest.param(
            """
hass.services.async_call(
    "light",
    LightService.TURN_ON,
    target={ATTR_ENTITY_ID: "light.kitchen"},
)
""",
            id="target_keyword_not_checked",
        ),
        pytest.param(
            """
hass.services.async_call(
    "light", LightService.TURN_ON, {"brightness": ATTR_ENTITY_ID}
)
""",
            id="constant_in_value",
        ),
    ],
)
def test_no_message(
    linter: UnittestLinter, target_key_checker: TargetKeyChecker, code: str
) -> None:
    """Test calls that are not reported."""
    root_node = astroid.parse(_IMPORTS + code, "tests.components.light.test_init")
    with assert_no_messages(linter):
        walk_checker(linter, target_key_checker, root_node)


def test_no_message_outside_tests(
    linter: UnittestLinter, target_key_checker: TargetKeyChecker
) -> None:
    """Test that calls outside test modules are not reported."""
    code = """
hass.services.async_call("light", LightService.TURN_ON, {ATTR_ENTITY_ID: "light.kitchen"})
"""
    root_node = astroid.parse(
        _IMPORTS + code, "homeassistant.components.google_assistant.trait"
    )
    with assert_no_messages(linter):
        walk_checker(linter, target_key_checker, root_node)


@pytest.mark.parametrize(
    ("code", "key"),
    [
        pytest.param(
            """
hass.services.async_call("light", LightService.TURN_ON, {ATTR_ENTITY_ID: "light.kitchen"})
""",
            "ATTR_ENTITY_ID",
            id="attr_entity_id",
        ),
        pytest.param(
            """
hass.services.async_call(
    "light",
    LightService.TURN_ON,
    {CommonServiceArgument.ENTITY_ID: "light.kitchen"},
)
""",
            "CommonServiceArgument.ENTITY_ID",
            id="common_service_argument",
        ),
        pytest.param(
            """
hass.services.async_call(
    "light",
    LightService.TURN_ON,
    service_data={CONF_ENTITY_ID: "light.kitchen"},
)
""",
            "CONF_ENTITY_ID",
            id="service_data_keyword",
        ),
    ],
)
def test_message(
    linter: UnittestLinter,
    target_key_checker: TargetKeyChecker,
    code: str,
    key: str,
) -> None:
    """Test calls whose target key is reported."""
    root_node = astroid.parse(_IMPORTS + code, "tests.components.light.test_init")
    key_node = next(
        node
        for node in root_node.nodes_of_class(
            (astroid.nodes.Name, astroid.nodes.Attribute)
        )
        if node.as_string() == key and isinstance(node.parent, astroid.nodes.Dict)
    )
    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-action-target-key",
            node=key_node,
            args=(key,),
            line=key_node.lineno,
            col_offset=key_node.col_offset,
            end_line=key_node.end_lineno,
            end_col_offset=key_node.end_col_offset,
        ),
    ):
        walk_checker(linter, target_key_checker, root_node)
