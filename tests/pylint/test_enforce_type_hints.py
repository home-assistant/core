"""Tests for pylint hass_enforce_type_hints plugin."""
# pylint:disable=protected-access
from __future__ import annotations

import re
from types import ModuleType
from unittest.mock import patch

import astroid
from pylint.checkers import BaseChecker
import pylint.testutils
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

from . import assert_adds_messages, assert_no_messages


@pytest.mark.parametrize(
    ("module_name", "expected_platform", "in_platforms"),
    [
        ("homeassistant", None, False),
        ("homeassistant.components", None, False),
        ("homeassistant.components.pylint_test", "__init__", False),
        ("homeassistant.components.pylint_test.config_flow", "config_flow", False),
        ("homeassistant.components.pylint_test.light", "light", True),
        ("homeassistant.components.pylint_test.light.v1", None, False),
    ],
)
def test_regex_get_module_platform(
    hass_enforce_type_hints: ModuleType,
    module_name: str,
    expected_platform: str | None,
    in_platforms: bool,
) -> None:
    """Test _get_module_platform regex."""
    platform = hass_enforce_type_hints._get_module_platform(module_name)

    assert platform == expected_platform
    assert (platform in hass_enforce_type_hints._PLATFORMS) == in_platforms


@pytest.mark.parametrize(
    ("string", "expected_x", "expected_y", "expected_z", "expected_a"),
    [
        ("list[dict[str, str]]", "list", "dict", "str", "str"),
        ("list[dict[str, Any]]", "list", "dict", "str", "Any"),
    ],
)
def test_regex_x_of_y_of_z_comma_a(
    hass_enforce_type_hints: ModuleType,
    string: str,
    expected_x: str,
    expected_y: str,
    expected_z: str,
    expected_a: str,
) -> None:
    """Test x_of_y_of_z_comma_a regexes."""
    matchers: dict[str, re.Pattern] = hass_enforce_type_hints._TYPE_HINT_MATCHERS

    assert (match := matchers["x_of_y_of_z_comma_a"].match(string))
    assert match.group(0) == string
    assert match.group(1) == expected_x
    assert match.group(2) == expected_y
    assert match.group(3) == expected_z
    assert match.group(4) == expected_a


@pytest.mark.parametrize(
    ("string", "expected_x", "expected_y", "expected_z"),
    [
        ("Callable[..., None]", "Callable", "...", "None"),
        ("Callable[..., Awaitable[None]]", "Callable", "...", "Awaitable[None]"),
    ],
)
def test_regex_x_of_y_comma_z(
    hass_enforce_type_hints: ModuleType,
    string: str,
    expected_x: str,
    expected_y: str,
    expected_z: str,
) -> None:
    """Test x_of_y_comma_z regexes."""
    matchers: dict[str, re.Pattern] = hass_enforce_type_hints._TYPE_HINT_MATCHERS

    assert (match := matchers["x_of_y_comma_z"].match(string))
    assert match.group(0) == string
    assert match.group(1) == expected_x
    assert match.group(2) == expected_y
    assert match.group(3) == expected_z


@pytest.mark.parametrize(
    ("string", "expected_a", "expected_b"),
    [("DiscoveryInfoType | None", "DiscoveryInfoType", "None")],
)
def test_regex_a_or_b(
    hass_enforce_type_hints: ModuleType, string: str, expected_a: str, expected_b: str
) -> None:
    """Test a_or_b regexes."""
    matchers: dict[str, re.Pattern] = hass_enforce_type_hints._TYPE_HINT_MATCHERS

    assert (match := matchers["a_or_b"].match(string))
    assert match.group(0) == string
    assert match.group(1) == expected_a
    assert match.group(2) == expected_b


@pytest.mark.parametrize(
    "code",
    [
        """
    async def setup( #@
        arg1, arg2
    ):
        pass
    """
    ],
)
def test_ignore_no_annotations(
    hass_enforce_type_hints: ModuleType, type_hint_checker: BaseChecker, code: str
) -> None:
    """Ensure that _is_valid_type is not run if there are no annotations."""
    func_node = astroid.extract_node(
        code,
        "homeassistant.components.pylint_test",
    )
    type_hint_checker.visit_module(func_node.parent)

    with patch.object(
        hass_enforce_type_hints, "_is_valid_type", return_value=True
    ) as is_valid_type:
        type_hint_checker.visit_asyncfunctiondef(func_node)
        is_valid_type.assert_not_called()


@pytest.mark.parametrize(
    "code",
    [
        """
    async def setup( #@
        arg1, arg2
    ):
        pass
    """
    ],
)
def test_bypass_ignore_no_annotations(
    hass_enforce_type_hints: ModuleType, type_hint_checker: BaseChecker, code: str
) -> None:
    """Test `ignore-missing-annotations` option.

    Ensure that `_is_valid_type` is run if there are no annotations
    but `ignore-missing-annotations` option is forced to False.
    """
    # Set bypass option
    type_hint_checker.config.ignore_missing_annotations = False

    func_node = astroid.extract_node(
        code,
        "homeassistant.components.pylint_test",
    )
    type_hint_checker.visit_module(func_node.parent)

    with patch.object(
        hass_enforce_type_hints, "_is_valid_type", return_value=True
    ) as is_valid_type:
        type_hint_checker.visit_asyncfunctiondef(func_node)
        is_valid_type.assert_called()


@pytest.mark.parametrize(
    "code",
    [
        """
    async def setup( #@
        arg1: ArgHint, arg2
    ):
        pass
    """,
        """
    async def setup( #@
        arg1, arg2
    ) -> ReturnHint:
        pass
    """,
        """
    async def setup( #@
        arg1: ArgHint, arg2: ArgHint
    ) -> ReturnHint:
        pass
    """,
    ],
)
def test_dont_ignore_partial_annotations(
    hass_enforce_type_hints: ModuleType, type_hint_checker: BaseChecker, code: str
) -> None:
    """Ensure that _is_valid_type is run if there is at least one annotation."""
    func_node = astroid.extract_node(
        code,
        "homeassistant.components.pylint_test",
    )
    type_hint_checker.visit_module(func_node.parent)

    with patch.object(
        hass_enforce_type_hints, "_is_valid_type", return_value=True
    ) as is_valid_type:
        type_hint_checker.visit_asyncfunctiondef(func_node)
        is_valid_type.assert_called()


def test_invalid_discovery_info(
    linter: UnittestLinter, type_hint_checker: BaseChecker
) -> None:
    """Ensure invalid hints are rejected for discovery_info."""
    func_node, discovery_info_node = astroid.extract_node(
        """
    async def async_setup_scanner( #@
        hass: HomeAssistant,
        config: ConfigType,
        async_see: Callable[..., Awaitable[None]],
        discovery_info: dict[str, Any] | None = None, #@
    ) -> bool:
        pass
    """,
        "homeassistant.components.pylint_test.device_tracker",
    )
    type_hint_checker.visit_module(func_node.parent)

    with assert_adds_messages(
        linter,
        pylint.testutils.MessageTest(
            msg_id="hass-argument-type",
            node=discovery_info_node,
            args=(4, "DiscoveryInfoType | None"),
            line=6,
            col_offset=4,
            end_line=6,
            end_col_offset=41,
        ),
    ):
        type_hint_checker.visit_asyncfunctiondef(func_node)


def test_valid_discovery_info(
    linter: UnittestLinter, type_hint_checker: BaseChecker
) -> None:
    """Ensure valid hints are accepted for discovery_info."""
    func_node = astroid.extract_node(
        """
    async def async_setup_scanner( #@
        hass: HomeAssistant,
        config: ConfigType,
        async_see: Callable[..., Awaitable[None]],
        discovery_info: DiscoveryInfoType | None = None,
    ) -> bool:
        pass
    """,
        "homeassistant.components.pylint_test.device_tracker",
    )
    type_hint_checker.visit_module(func_node.parent)

    with assert_no_messages(linter):
        type_hint_checker.visit_asyncfunctiondef(func_node)


def test_invalid_list_dict_str_any(
    linter: UnittestLinter, type_hint_checker: BaseChecker
) -> None:
    """Ensure invalid hints are rejected for discovery_info."""
    func_node = astroid.extract_node(
        """
    async def async_get_triggers( #@
        hass: HomeAssistant,
        device_id: str
    ) -> list:
        pass
    """,
        "homeassistant.components.pylint_test.device_trigger",
    )
    type_hint_checker.visit_module(func_node.parent)

    with assert_adds_messages(
        linter,
        pylint.testutils.MessageTest(
            msg_id="hass-return-type",
            node=func_node,
            args=["list[dict[str, str]]", "list[dict[str, Any]]"],
            line=2,
            col_offset=0,
            end_line=2,
            end_col_offset=28,
        ),
    ):
        type_hint_checker.visit_asyncfunctiondef(func_node)


def test_valid_list_dict_str_any(
    linter: UnittestLinter, type_hint_checker: BaseChecker
) -> None:
    """Ensure valid hints are accepted for discovery_info."""
    func_node = astroid.extract_node(
        """
    async def async_get_triggers( #@
        hass: HomeAssistant,
        device_id: str
    ) -> list[dict[str, Any]]:
        pass
    """,
        "homeassistant.components.pylint_test.device_trigger",
    )
    type_hint_checker.visit_module(func_node.parent)

    with assert_no_messages(linter):
        type_hint_checker.visit_asyncfunctiondef(func_node)


def test_invalid_config_flow_step(
    linter: UnittestLinter, type_hint_checker: BaseChecker
) -> None:
    """Ensure invalid hints are rejected for ConfigFlow step."""
    class_node, func_node, arg_node = astroid.extract_node(
        """
    class ConfigFlow():
        pass

    class AxisFlowHandler( #@
        ConfigFlow, domain=AXIS_DOMAIN
    ):
        async def async_step_zeroconf( #@
            self,
            device_config: dict #@
        ):
            pass
    """,
        "homeassistant.components.pylint_test.config_flow",
    )
    type_hint_checker.visit_module(class_node.parent)

    with assert_adds_messages(
        linter,
        pylint.testutils.MessageTest(
            msg_id="hass-argument-type",
            node=arg_node,
            args=(2, "ZeroconfServiceInfo"),
            line=10,
            col_offset=8,
            end_line=10,
            end_col_offset=27,
        ),
        pylint.testutils.MessageTest(
            msg_id="hass-return-type",
            node=func_node,
            args="FlowResult",
            line=8,
            col_offset=4,
            end_line=8,
            end_col_offset=33,
        ),
    ):
        type_hint_checker.visit_classdef(class_node)


def test_valid_config_flow_step(
    linter: UnittestLinter, type_hint_checker: BaseChecker
) -> None:
    """Ensure valid hints are accepted for ConfigFlow step."""
    class_node = astroid.extract_node(
        """
    class ConfigFlow():
        pass

    class AxisFlowHandler( #@
        ConfigFlow, domain=AXIS_DOMAIN
    ):
        async def async_step_zeroconf(
            self,
            device_config: ZeroconfServiceInfo
        ) -> FlowResult:
            pass
    """,
        "homeassistant.components.pylint_test.config_flow",
    )
    type_hint_checker.visit_module(class_node.parent)

    with assert_no_messages(linter):
        type_hint_checker.visit_classdef(class_node)


def test_invalid_config_flow_async_get_options_flow(
    linter: UnittestLinter, type_hint_checker: BaseChecker
) -> None:
    """Ensure invalid hints are rejected for ConfigFlow async_get_options_flow."""
    class_node, func_node, arg_node = astroid.extract_node(
        """
    class ConfigFlow():
        pass

    class AxisOptionsFlow():
        pass

    class AxisFlowHandler( #@
        ConfigFlow, domain=AXIS_DOMAIN
    ):
        def async_get_options_flow( #@
            config_entry #@
        ) -> AxisOptionsFlow:
            return AxisOptionsFlow(config_entry)
    """,
        "homeassistant.components.pylint_test.config_flow",
    )
    type_hint_checker.visit_module(class_node.parent)

    with assert_adds_messages(
        linter,
        pylint.testutils.MessageTest(
            msg_id="hass-argument-type",
            node=arg_node,
            args=(1, "ConfigEntry"),
            line=12,
            col_offset=8,
            end_line=12,
            end_col_offset=20,
        ),
        pylint.testutils.MessageTest(
            msg_id="hass-return-type",
            node=func_node,
            args="OptionsFlow",
            line=11,
            col_offset=4,
            end_line=11,
            end_col_offset=30,
        ),
    ):
        type_hint_checker.visit_classdef(class_node)


def test_valid_config_flow_async_get_options_flow(
    linter: UnittestLinter, type_hint_checker: BaseChecker
) -> None:
    """Ensure valid hints are accepted for ConfigFlow async_get_options_flow."""
    class_node = astroid.extract_node(
        """
    class ConfigFlow():
        pass

    class OptionsFlow():
        pass

    class AxisOptionsFlow(OptionsFlow):
        pass

    class OtherOptionsFlow(OptionsFlow):
        pass

    class AxisFlowHandler( #@
        ConfigFlow, domain=AXIS_DOMAIN
    ):
        def async_get_options_flow(
            config_entry: ConfigEntry
        ) -> AxisOptionsFlow | OtherOptionsFlow | OptionsFlow:
            if self.use_other:
                return OtherOptionsFlow(config_entry)
            return AxisOptionsFlow(config_entry)

    """,
        "homeassistant.components.pylint_test.config_flow",
    )
    type_hint_checker.visit_module(class_node.parent)

    with assert_no_messages(linter):
        type_hint_checker.visit_classdef(class_node)
