"""Tests for pylint hass enforce non list comprehensions plugin."""
import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import UNDEFINED
from pylint.testutils import MessageTest, UnittestLinter
from pylint.utils import ASTWalker
import pytest

from . import assert_adds_messages, assert_no_messages


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
        async_add_entities(entity for entity in entities)
        """,
            id="generator_expression",
        ),
        pytest.param(
            """
        entities: list[Sensor] = []

        async_add_entities(entities)
        """,
            id="passing_list",
        ),
        pytest.param(
            """
        async_add_entities([entity for entity in entities], True)
        """,
            id="list_comprehension_with_update_before_add",
        ),
    ],
)
def test_enforce_sorted_platforms(
    linter: UnittestLinter,
    enforce_non_list_comprehensions_checker: BaseChecker,
    code: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_non_list_comprehensions_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_enforce_sorted_platforms_bad(
    linter: UnittestLinter,
    enforce_non_list_comprehensions_checker: BaseChecker,
) -> None:
    """Bad test case."""
    call_node = astroid.extract_node(
        """
    async_add_entities([entity for entity in entities])
    """,
        "homeassistant.components.pylint_test",
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-enforce-non-list-comprehensions",
            line=2,
            node=call_node,
            args=None,
            confidence=UNDEFINED,
            col_offset=0,
            end_line=2,
            end_col_offset=51,
        ),
    ):
        enforce_non_list_comprehensions_checker.visit_call(call_node)
