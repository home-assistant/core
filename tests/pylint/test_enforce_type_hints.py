"""Tests for pylint hass_enforce_type_hints plugin."""
# pylint:disable=protected-access

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
def test_ignore_not_annotations(
    hass_enforce_type_hints: ModuleType, type_hint_checker: BaseChecker, code: str
) -> None:
    """Ensure that _is_valid_type is not run if there are no annotations."""
    func_node = astroid.extract_node(code)

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
    func_node = astroid.extract_node(code)

    with patch.object(
        hass_enforce_type_hints, "_is_valid_type", return_value=True
    ) as is_valid_type:
        type_hint_checker.visit_asyncfunctiondef(func_node)
        is_valid_type.assert_called()


def test_invalid_discovery_info(
    linter: UnittestLinter, type_hint_checker: BaseChecker
) -> None:
    """Ensure invalid hints are rejected for discovery_info."""
    type_hint_checker.module = "homeassistant.components.pylint_test.device_tracker"
    func_node, discovery_info_node = astroid.extract_node(
        """
    async def async_setup_scanner( #@
        hass: HomeAssistant,
        config: ConfigType,
        async_see: Callable[..., Awaitable[None]],
        discovery_info: dict[str, Any] | None = None, #@
    ) -> bool:
        pass
    """
    )

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
    type_hint_checker.module = "homeassistant.components.pylint_test.device_tracker"
    func_node = astroid.extract_node(
        """
    async def async_setup_scanner( #@
        hass: HomeAssistant,
        config: ConfigType,
        async_see: Callable[..., Awaitable[None]],
        discovery_info: DiscoveryInfoType | None = None,
    ) -> bool:
        pass
    """
    )

    with assert_no_messages(linter):
        type_hint_checker.visit_asyncfunctiondef(func_node)
