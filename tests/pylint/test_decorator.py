"""Tests for pylint hass_enforce_type_hints plugin."""

from __future__ import annotations

import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import UNDEFINED
from pylint.testutils import MessageTest
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker

from . import assert_adds_messages, assert_no_messages


def test_good_callback(linter: UnittestLinter, decorator_checker: BaseChecker) -> None:
    """Test good `@callback` decorator."""
    code = """
    from homeassistant.core import callback

    @callback
    def setup(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code)
    walker = ASTWalker(linter)
    walker.add_checker(decorator_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_bad_callback(linter: UnittestLinter, decorator_checker: BaseChecker) -> None:
    """Test bad `@callback` decorator."""
    code = """
    from homeassistant.core import callback

    @callback
    async def setup(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code)
    walker = ASTWalker(linter)
    walker.add_checker(decorator_checker)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-async-callback-decorator",
            line=5,
            node=root_node.body[1],
            args=None,
            confidence=UNDEFINED,
            col_offset=0,
            end_line=5,
            end_col_offset=15,
        ),
    ):
        walker.walk(root_node)
