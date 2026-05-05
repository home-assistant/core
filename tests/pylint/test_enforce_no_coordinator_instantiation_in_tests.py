"""Tests for the hass_enforce_no_coordinator_instantiation_in_tests plugin."""

from __future__ import annotations

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils import MessageTest
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
import pytest

from . import assert_adds_messages, assert_no_messages

# Stub of the real DataUpdateCoordinator class hierarchy so that astroid can
# resolve the ``inherits from coordinator base`` check. The ``qname()`` of
# these classes will be evaluated against the configured base list.
COORDINATOR_STUB = """
import sys
import types

_pkg = types.ModuleType("homeassistant")
_helpers = types.ModuleType("homeassistant.helpers")
_uc = types.ModuleType("homeassistant.helpers.update_coordinator")
sys.modules["homeassistant"] = _pkg
sys.modules["homeassistant.helpers"] = _helpers
sys.modules["homeassistant.helpers.update_coordinator"] = _uc


class DataUpdateCoordinator:
    pass


class TimestampDataUpdateCoordinator(DataUpdateCoordinator):
    pass


_uc.DataUpdateCoordinator = DataUpdateCoordinator
_uc.TimestampDataUpdateCoordinator = TimestampDataUpdateCoordinator
DataUpdateCoordinator.__module__ = "homeassistant.helpers.update_coordinator"
TimestampDataUpdateCoordinator.__module__ = (
    "homeassistant.helpers.update_coordinator"
)
"""


def _parse(code: str, module_name: str) -> astroid.Module:
    """Parse code, ensuring the coordinator stub module is registered."""
    # Register the coordinator base classes in astroid's builder by parsing
    # them as a separate module that the test code imports from.
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


@pytest.mark.parametrize(
    ("code", "module_name"),
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
            id="multiple_inheritance",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class FooCoordinator(DataUpdateCoordinator):
    pass


def test_thing(hass, entry):
    from unittest.mock import AsyncMock
    coordinator = AsyncMock(spec=FooCoordinator)
    other = FooCoordinator(hass, entry)
""",
            "tests.components.foo.test_coordinator",
            id="alongside_mock_only_real_call_flagged",
        ),
    ],
)
def test_enforce_no_coordinator_instantiation_in_tests_bad(
    linter: UnittestLinter,
    enforce_no_coordinator_instantiation_in_tests_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Bad cases: coordinators instantiated directly inside an integration test."""
    root_node = _parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(enforce_no_coordinator_instantiation_in_tests_checker)

    # Find the last ``FooCoordinator(...)`` call node in the tree -- that's
    # the one we expect to trigger the message.
    call_nodes = [
        node
        for node in root_node.nodes_of_class(astroid.nodes.Call)
        if isinstance(node.func, astroid.nodes.Name)
        and node.func.name == "FooCoordinator"
    ]
    expected_node = call_nodes[-1]

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-no-coordinator-instantiation-in-tests",
            node=expected_node,
            line=expected_node.lineno,
            args=("FooCoordinator",),
            col_offset=expected_node.col_offset,
            end_line=expected_node.position.end_lineno
            if expected_node.position
            else expected_node.end_lineno,
            end_col_offset=expected_node.position.end_col_offset
            if expected_node.position
            else expected_node.end_col_offset,
        ),
    ):
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
    from unittest.mock import AsyncMock
    coordinator = AsyncMock(spec=FooCoordinator)
""",
            "tests.components.foo.test_coordinator",
            id="mock_wrapping_a_coordinator_class_is_not_a_call_to_it",
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
