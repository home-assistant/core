"""Tests for the action target key checker."""

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.actions.target_key import TargetKeyChecker
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

_ENUM_IMPORTS = """
from homeassistant.components.light import LightService
from homeassistant.components.zwave_js.const import ZWaveJSService
"""


@pytest.fixture(name="target_key_checker")
def target_key_checker_fixture(linter: UnittestLinter) -> TargetKeyChecker:
    """Fixture to provide a target key checker."""
    return TargetKeyChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
hass.services.async_call(
    "light",
    LightService.TURN_ON,
    target={TargetKey.ENTITY_ID: "light.kitchen", "area_id": "kitchen"},
)
""",
            id="target_key_and_string_literal",
        ),
        pytest.param(
            """
hass.services.async_call(
    "light",
    LightService.TURN_ON,
    target={
        TargetKey.AREA_ID: "kitchen",
        CONF_EXCLUDE: {TargetKey.ENTITY_ID: "light.pantry"},
    },
)
""",
            id="exclude_block",
        ),
        pytest.param(
            """
hass.services.async_call("light", LightService.TURN_ON, target=target)
""",
            id="target_not_a_dict",
        ),
        pytest.param(
            """
hass.services.async_call("light", LightService.TURN_ON, {ATTR_ENTITY_ID: "light.kitchen"})
""",
            id="data_unresolved_action",
        ),
        pytest.param(
            """
create_target_condition(hass, target={ATTR_ENTITY_ID: "light.kitchen"})
""",
            id="not_an_action_call",
        ),
    ],
)
def test_no_message(
    linter: UnittestLinter, target_key_checker: TargetKeyChecker, code: str
) -> None:
    """Test calls that are not reported."""
    root_node = astroid.parse(code, "tests.components.light.test_init")
    with assert_no_messages(linter):
        walk_checker(linter, target_key_checker, root_node)


def test_message_in_integration_code(
    linter: UnittestLinter, target_key_checker: TargetKeyChecker
) -> None:
    """Test that calls in integration code are reported too."""
    code = """
hass.services.async_call("light", "turn_on", target={ATTR_ENTITY_ID: "light.kitchen"})
"""
    root_node = astroid.parse(code, "homeassistant.components.climate.intent")
    key_node = next(
        node
        for node in root_node.nodes_of_class(astroid.nodes.Name)
        if node.name == "ATTR_ENTITY_ID"
    )
    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-action-target-key",
            node=key_node,
            args=("ATTR_ENTITY_ID", "TargetKey.ENTITY_ID"),
            line=key_node.lineno,
            col_offset=key_node.col_offset,
            end_line=key_node.end_lineno,
            end_col_offset=key_node.end_col_offset,
        ),
    ):
        walk_checker(linter, target_key_checker, root_node)


@pytest.mark.parametrize(
    ("code", "key", "replacement"),
    [
        pytest.param(
            """
hass.services.async_call(
    "light",
    LightService.TURN_ON,
    target={ATTR_ENTITY_ID: "light.kitchen"},
)
""",
            "ATTR_ENTITY_ID",
            "TargetKey.ENTITY_ID",
            id="attr_entity_id",
        ),
        pytest.param(
            """
hass.services.async_call("light", "turn_on", target={ATTR_AREA_ID: "kitchen"})
""",
            "ATTR_AREA_ID",
            "TargetKey.AREA_ID",
            id="attr_area_id",
        ),
        pytest.param(
            """
hass.services.async_call("light", "turn_on", target={CONF_LABEL_ID: "christmas"})
""",
            "CONF_LABEL_ID",
            "TargetKey.LABEL_ID",
            id="conf_label_id",
        ),
        pytest.param(
            """
hass.services.async_call(
    "light",
    LightService.TURN_ON,
    target={CommonServiceArgument.DEVICE_ID: "device-1"},
)
""",
            "CommonServiceArgument.DEVICE_ID",
            "TargetKey.DEVICE_ID",
            id="common_service_argument",
        ),
        pytest.param(
            """
hass.services.async_call(
    "light",
    LightService.TURN_ON,
    target={
        TargetKey.ENTITY_ID: "all",
        CONF_EXCLUDE: {ATTR_ENTITY_ID: "light.pantry"},
    },
)
""",
            "ATTR_ENTITY_ID",
            "TargetKey.ENTITY_ID",
            id="exclude_block_constant_key",
        ),
        pytest.param(
            """
hass.services.async_call(
    "light",
    LightService.TURN_ON,
    target={TargetKey.AREA_ID: "kitchen", "exclude": {ATTR_LABEL_ID: "christmas"}},
)
""",
            "ATTR_LABEL_ID",
            "TargetKey.LABEL_ID",
            id="exclude_block_string_key",
        ),
    ],
)
def test_message(
    linter: UnittestLinter,
    target_key_checker: TargetKeyChecker,
    code: str,
    key: str,
    replacement: str,
) -> None:
    """Test target keys that are reported."""
    root_node = astroid.parse(code, "tests.components.light.test_init")
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
            args=(key, replacement),
            line=key_node.lineno,
            col_offset=key_node.col_offset,
            end_line=key_node.end_lineno,
            end_col_offset=key_node.end_col_offset,
        ),
    ):
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
    {"brightness": 100, CommonServiceArgument.ENTITY_ID: "light.kitchen"},
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
def test_data_message(
    linter: UnittestLinter,
    target_key_checker: TargetKeyChecker,
    code: str,
    key: str,
) -> None:
    """Test target keys in the data of an action call that are reported."""
    root_node = astroid.parse(_ENUM_IMPORTS + code, "tests.components.light.test_init")
    key_node = next(
        node
        for node in root_node.nodes_of_class(
            (astroid.nodes.Name, astroid.nodes.Attribute)
        )
        if node.as_string() == key
    )
    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-action-target-key",
            node=key_node,
            args=(key, "TargetKey.ENTITY_ID"),
            line=key_node.lineno,
            col_offset=key_node.col_offset,
            end_line=key_node.end_lineno,
            end_col_offset=key_node.end_col_offset,
        ),
    ):
        walk_checker(linter, target_key_checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
hass.services.async_call(
    "light", LightService.TURN_ON, {TargetKey.ENTITY_ID: "light.kitchen"}
)
""",
            "tests.components.light.test_init",
            id="target_key",
        ),
        pytest.param(
            """
hass.services.async_call("light", LightService.TURN_ON, {"entity_id": "light.kitchen"})
""",
            "tests.components.light.test_init",
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
            "tests.components.zwave_js.test_services",
            id="real_entity_id_field",
        ),
        pytest.param(
            """
hass.services.async_call("light", "turn_on", {ATTR_ENTITY_ID: "light.kitchen"})
""",
            "tests.components.light.test_init",
            id="action_not_an_enum_member",
        ),
        pytest.param(
            """
hass.services.async_call("light", LightService.UNKNOWN, {ATTR_ENTITY_ID: "light.kitchen"})
""",
            "tests.components.light.test_init",
            id="unknown_enum_member",
        ),
        pytest.param(
            """
hass.services.async_call("light", LightService.TURN_ON, {"brightness": ATTR_ENTITY_ID})
""",
            "tests.components.light.test_init",
            id="constant_in_value",
        ),
        pytest.param(
            """
hass.services.async_call("light", LightService.TURN_ON, data)
""",
            "tests.components.light.test_init",
            id="data_not_a_dict",
        ),
        pytest.param(
            """
hass.services.async_call("light", LightService.TURN_ON, {**data})
""",
            "tests.components.light.test_init",
            id="dict_unpack",
        ),
        pytest.param(
            """
hass.services.async_call("light", LightService.TURN_ON, {ATTR_ENTITY_ID: "light.kitchen"})
""",
            "homeassistant.components.google_assistant.trait",
            id="integration_code",
        ),
    ],
)
def test_data_no_message(
    linter: UnittestLinter,
    target_key_checker: TargetKeyChecker,
    code: str,
    module_name: str,
) -> None:
    """Test data of action calls that is not reported."""
    root_node = astroid.parse(_ENUM_IMPORTS + code, module_name)
    with assert_no_messages(linter):
        walk_checker(linter, target_key_checker, root_node)
