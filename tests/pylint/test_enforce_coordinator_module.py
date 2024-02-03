"""Tests for pylint hass_enforce_coordinator_module plugin."""
from __future__ import annotations

import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import UNDEFINED
from pylint.testutils import MessageTest
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
import pytest

from . import assert_adds_messages, assert_no_messages


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
    class DataUpdateCoordinator:
        pass

    class TestCoordinator(DataUpdateCoordinator):
        pass
    """,
            id="simple",
        ),
        pytest.param(
            """
    class DataUpdateCoordinator:
        pass

    class TestCoordinator(DataUpdateCoordinator):
        pass

    class TestCoordinator2(TestCoordinator):
        pass
    """,
            id="nested",
        ),
    ],
)
def test_enforce_coordinator_module_good(
    linter: UnittestLinter, enforce_coordinator_module_checker: BaseChecker, code: str
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test.coordinator")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_coordinator_module_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_enforce_coordinator_module_bad_simple(
    linter: UnittestLinter,
    enforce_coordinator_module_checker: BaseChecker,
) -> None:
    """Bad test case with coordinator extending directly."""
    root_node = astroid.parse(
        """
    class DataUpdateCoordinator:
        pass

    class TestCoordinator(DataUpdateCoordinator):
        pass
    """,
        "homeassistant.components.pylint_test",
    )
    walker = ASTWalker(linter)
    walker.add_checker(enforce_coordinator_module_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-enforce-coordinator-module",
            line=5,
            node=root_node.body[1],
            args=None,
            confidence=UNDEFINED,
            col_offset=0,
            end_line=5,
            end_col_offset=21,
        ),
    ):
        walker.walk(root_node)


def test_enforce_coordinator_module_bad_nested(
    linter: UnittestLinter,
    enforce_coordinator_module_checker: BaseChecker,
) -> None:
    """Bad test case with nested coordinators."""
    root_node = astroid.parse(
        """
    class DataUpdateCoordinator:
        pass

    class TestCoordinator(DataUpdateCoordinator):
        pass

    class NopeCoordinator(TestCoordinator):
        pass
    """,
        "homeassistant.components.pylint_test",
    )
    walker = ASTWalker(linter)
    walker.add_checker(enforce_coordinator_module_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-enforce-coordinator-module",
            line=5,
            node=root_node.body[1],
            args=None,
            confidence=UNDEFINED,
            col_offset=0,
            end_line=5,
            end_col_offset=21,
        ),
        MessageTest(
            msg_id="hass-enforce-coordinator-module",
            line=8,
            node=root_node.body[2],
            args=None,
            confidence=UNDEFINED,
            col_offset=0,
            end_line=8,
            end_col_offset=21,
        ),
    ):
        walker.walk(root_node)
