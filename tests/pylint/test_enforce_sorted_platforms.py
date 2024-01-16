"""Tests for pylint hass_enforce_sorted_platforms plugin."""
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
        PLATFORMS = [Platform.SENSOR]
        """,
            id="one_platform",
        ),
        pytest.param(
            """
        PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]
        """,
            id="multiple_platforms",
        ),
    ],
)
def test_enforce_sorted_platforms(
    linter: UnittestLinter,
    enforce_sorted_platforms_checker: BaseChecker,
    code: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_sorted_platforms_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_enforce_sorted_platforms_bad(
    linter: UnittestLinter,
    enforce_sorted_platforms_checker: BaseChecker,
) -> None:
    """Bad test case."""
    assign_node = astroid.extract_node(
        """
    PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
    """,
        "homeassistant.components.pylint_test",
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-enforce-sorted-platforms",
            line=2,
            node=assign_node,
            args=None,
            confidence=UNDEFINED,
            col_offset=0,
            end_line=2,
            end_col_offset=70,
        ),
    ):
        enforce_sorted_platforms_checker.visit_assign(assign_node)
