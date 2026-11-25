"""Tests for the type_checking_block pylint checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.type_checking_block import (
    HassTypeCheckingBlockChecker,
)
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

_MSG_ID = "home-assistant-type-checking-block-position"
_MODULE_NAME = "homeassistant.components.pylint_test.sensor"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> HassTypeCheckingBlockChecker:
    """Fixture to provide the type_checking_block checker."""
    return HassTypeCheckingBlockChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import MyConfigEntry
from .const import DOMAIN
""",
            id="import_from_after_block",
        ),
        pytest.param(
            """
import typing

if typing.TYPE_CHECKING:
    from . import MyConfigEntry

import logging
""",
            id="import_after_typing_attribute_block",
        ),
        pytest.param(
            """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import MyConfigEntry

_LOGGER = None

from .const import DOMAIN
""",
            id="import_after_code",
        ),
    ],
)
def test_import_after_type_checking_block(
    linter: UnittestLinter, checker: HassTypeCheckingBlockChecker, code: str
) -> None:
    """Test an import after the ``TYPE_CHECKING`` block is flagged."""
    root_node = astroid.parse(code, _MODULE_NAME)
    block = next(root_node.nodes_of_class(nodes.If))
    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id=_MSG_ID,
            node=block,
            line=block.lineno,
            col_offset=block.col_offset,
            end_line=block.end_lineno,
            end_col_offset=block.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from typing import TYPE_CHECKING

from .const import DOMAIN

if TYPE_CHECKING:
    from . import MyConfigEntry
""",
            id="block_after_imports",
        ),
        pytest.param(
            """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import MyConfigEntry

def setup() -> None:
    from .const import DOMAIN
""",
            id="function_import_after_block",
        ),
        pytest.param(
            """
import sys

if sys.version_info >= (3, 14):
    import json
from .const import DOMAIN
""",
            id="other_condition",
        ),
    ],
)
def test_type_checking_block_position_ok(
    linter: UnittestLinter, checker: HassTypeCheckingBlockChecker, code: str
) -> None:
    """Test a ``TYPE_CHECKING`` block after all imports is not flagged."""
    root_node = astroid.parse(code, _MODULE_NAME)
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)
