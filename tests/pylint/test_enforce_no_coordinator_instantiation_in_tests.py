"""Tests for the hass_enforce_no_coordinator_instantiation_in_tests plugin."""

from __future__ import annotations

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils import MessageTest
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
import pytest

from . import assert_adds_messages, assert_no_messages


def _parse(code: str, module_name: str) -> astroid.Module:
    """Parse code, ensuring the coordinator stub module is registered."""
    # Register the coordinator base classes in astroid's module cache so the
    # checker can resolve them via inference.
    astroid.parse(
        """
class DataUpdateCoordinator:
    pass


class TimestampDataUpdateCoordinator(DataUpdateCoordinator):
    pass
""",
        module_name="homeassistant.helpers.update_coordinator",
    )
    return astroid.parse(code, module_name=module_name)


def _expected_message(node: astroid.nodes.Call, name: str) -> MessageTest:
    """Build the expected MessageTest for a flagged Call node."""
    return MessageTest(
        msg_id="hass-no-coordinator-instantiation-in-tests",
        node=node,
        line=node.lineno,
        args=(name,),
        col_offset=node.col_offset,
        end_line=node.position.end_lineno if node.position else node.end_lineno,
        end_col_offset=node.position.end_col_offset
        if node.position
        else node.end_col_offset,
    )


@pytest.mark.parametrize(
    ("code", "module_name", "expected_calls"),
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class FooCoordinator(DataUpdateCoordinator):
    pass


def test_thing(hass, entry):
    coordinator = FooCoordinator(hass, entry)
""",
            "tests.components.foo.test_coordinator",
            ((10, "FooCoordinator"),),
            id="direct_data_update_coordinator_subclass",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
)


class FooCoordinator(TimestampDataUpdateCoordinator):
    pass


def test_thing(hass, entry):
    coordinator = FooCoordinator(hass, entry)
""",
            "tests.components.foo.test_coordinator",
            ((12, "FooCoordinator"),),
            id="timestamp_data_update_coordinator_subclass",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class Mixin:
    pass


class FooCoordinator(Mixin, DataUpdateCoordinator):
    pass


def test_thing(hass, entry):
    coordinator = FooCoordinator(hass, entry)
""",
            "tests.components.foo.test_other",
            ((14, "FooCoordinator"),),
            id="multiple_inheritance",
        ),
        pytest.param(
            """
from unittest.mock import AsyncMock

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class FooCoordinator(DataUpdateCoordinator):
    pass


def test_thing(hass, entry):
    coordinator = AsyncMock(spec=FooCoordinator)
""",
            "tests.components.foo.test_coordinator",
            ((12, "FooCoordinator"),),
            id="async_mock_with_spec_kwarg",
        ),
        pytest.param(
            """
from unittest.mock import MagicMock

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class FooCoordinator(DataUpdateCoordinator):
    pass


def test_thing(hass, entry):
    coordinator = MagicMock(spec=FooCoordinator)
""",
            "tests.components.foo.test_coordinator",
            ((12, "FooCoordinator"),),
            id="magic_mock_with_spec_kwarg",
        ),
        pytest.param(
            """
from unittest.mock import create_autospec

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class FooCoordinator(DataUpdateCoordinator):
    pass


def test_thing(hass, entry):
    coordinator = create_autospec(FooCoordinator)
""",
            "tests.components.foo.test_coordinator",
            ((12, "FooCoordinator"),),
            id="create_autospec_positional",
        ),
        pytest.param(
            """
from unittest.mock import AsyncMock

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class FooCoordinator(DataUpdateCoordinator):
    pass


def test_thing(hass, entry):
    coordinator = AsyncMock(spec=FooCoordinator)
    other = FooCoordinator(hass, entry)
""",
            "tests.components.foo.test_coordinator",
            ((12, "FooCoordinator"), (13, "FooCoordinator")),
            id="alongside_mock_both_flagged",
        ),
        pytest.param(
            """
from unittest.mock import patch


def test_thing(hass, entry):
    with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator"):
        pass
""",
            "tests.components.foo.test_coordinator",
            ((6, "DataUpdateCoordinator"),),
            id="patch_string_target",
        ),
        pytest.param(
            """
from unittest.mock import patch

from homeassistant.helpers import update_coordinator


def test_thing(hass, entry):
    with patch.object(update_coordinator, "DataUpdateCoordinator"):
        pass
""",
            "tests.components.foo.test_coordinator",
            ((8, "DataUpdateCoordinator"),),
            id="patch_object_target",
        ),
    ],
)
def test_enforce_no_coordinator_instantiation_in_tests_bad(
    linter: UnittestLinter,
    enforce_no_coordinator_instantiation_in_tests_checker: BaseChecker,
    code: str,
    module_name: str,
    expected_calls: tuple[tuple[int, str], ...],
) -> None:
    """Bad cases: coordinator usage that should be flagged in integration tests."""
    root_node = _parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_no_coordinator_instantiation_in_tests_checker)

    expected_lines = {line for line, _ in expected_calls}
    nodes_by_line = {
        node.lineno: node
        for node in root_node.nodes_of_class(astroid.nodes.Call)
        if node.lineno in expected_lines
    }
    assert len(nodes_by_line) == len(expected_lines)

    expected_messages = [
        _expected_message(nodes_by_line[line], name) for line, name in expected_calls
    ]

    with assert_adds_messages(linter, *expected_messages):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class FooCoordinator(DataUpdateCoordinator):
    pass


def setup_thing(hass, entry):
    coordinator = FooCoordinator(hass, entry)
""",
            "homeassistant.components.foo.coordinator",
            id="production_code_is_not_flagged",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class FooCoordinator(DataUpdateCoordinator):
    pass


def make_coordinator(hass, entry):
    return FooCoordinator(hass, entry)
""",
            "tests.components.foo.common",
            id="non_test_module_is_not_flagged",
        ),
        pytest.param(
            """
class NotACoordinator:
    pass


class FooCoordinator(NotACoordinator):
    pass


def test_thing(hass, entry):
    coordinator = FooCoordinator(hass, entry)
""",
            "tests.components.foo.test_coordinator",
            id="class_named_coordinator_but_not_subclass",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class FooCoordinator(DataUpdateCoordinator):
    pass


def test_thing(hass, entry):
    coordinator = FooCoordinator(hass, entry)
""",
            "tests.helpers.test_update_coordinator",
            id="path_outside_components_is_not_flagged",
        ),
        pytest.param(
            """
from unittest.mock import patch


def test_thing(hass, entry):
    with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.NOT_A_THING"):
        pass
""",
            "tests.components.foo.test_coordinator",
            id="patch_unresolvable_target_is_not_flagged",
        ),
        pytest.param(
            """
from unittest.mock import patch


def test_thing(hass, entry):
    with patch("homeassistant.components.foo.async_setup_entry"):
        pass
""",
            "tests.components.foo.test_init",
            id="patch_non_coordinator_string_target_is_not_flagged",
        ),
    ],
)
def test_enforce_no_coordinator_instantiation_in_tests_good(
    linter: UnittestLinter,
    enforce_no_coordinator_instantiation_in_tests_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Good cases: nothing should be flagged."""
    root_node = _parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_no_coordinator_instantiation_in_tests_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
