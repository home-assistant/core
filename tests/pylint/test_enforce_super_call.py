"""Tests for pylint hass_enforce_super_call plugin."""

from __future__ import annotations

from types import ModuleType
from unittest.mock import patch

import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import INFERENCE
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
    class Entity:
        async def async_added_to_hass(self) -> None:
            pass
    """,
            id="no_parent",
        ),
        pytest.param(
            """
    class Entity:
        async def async_added_to_hass(self) -> None:
            \"\"\"Some docstring.\"\"\"

    class Child(Entity):
        async def async_added_to_hass(self) -> None:
            x = 2
        """,
            id="empty_parent_implementation",
        ),
        pytest.param(
            """
    class Entity:
        async def async_added_to_hass(self) -> None:
            \"\"\"Some docstring.\"\"\"
            pass

    class Child(Entity):
        async def async_added_to_hass(self) -> None:
            x = 2
        """,
            id="empty_parent_implementation2",
        ),
        pytest.param(
            """
    class Entity:
        async def async_added_to_hass(self) -> None:
            x = 2

    class Child(Entity):
        async def async_added_to_hass(self) -> None:
            await super().async_added_to_hass()
        """,
            id="correct_super_call",
        ),
        pytest.param(
            """
    class Entity:
        async def async_added_to_hass(self) -> None:
            x = 2

    class Child(Entity):
        async def async_added_to_hass(self) -> None:
            return await super().async_added_to_hass()
        """,
            id="super_call_in_return",
        ),
        pytest.param(
            """
    class Entity:
        def added_to_hass(self) -> None:
            x = 2

    class Child(Entity):
        def added_to_hass(self) -> None:
            super().added_to_hass()
        """,
            id="super_call_not_async",
        ),
        pytest.param(
            """
    class Entity:
        async def async_added_to_hass(self) -> None:
            \"\"\"\"\"\"

    class Coordinator:
        async def async_added_to_hass(self) -> None:
            x = 2

    class Child(Entity, Coordinator):
        async def async_added_to_hass(self) -> None:
            await super().async_added_to_hass()
        """,
            id="multiple_inheritance",
        ),
        pytest.param(
            """
        async def async_added_to_hass() -> None:
            x = 2
        """,
            id="not_a_method",
        ),
    ],
)
def test_enforce_super_call(
    linter: UnittestLinter,
    hass_enforce_super_call: ModuleType,
    super_call_checker: BaseChecker,
    code: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(super_call_checker)

    with (
        patch.object(
            hass_enforce_super_call,
            "METHODS",
            new={"added_to_hass", "async_added_to_hass"},
        ),
        assert_no_messages(linter),
    ):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "node_idx"),
    [
        pytest.param(
            """
    class Entity:
        def added_to_hass(self) -> None:
            x = 2

    class Child(Entity):
        def added_to_hass(self) -> None:
            x = 3
    """,
            1,
            id="no_super_call",
        ),
        pytest.param(
            """
    class Entity:
        async def async_added_to_hass(self) -> None:
            x = 2

    class Child(Entity):
        async def async_added_to_hass(self) -> None:
            x = 3
    """,
            1,
            id="no_super_call_async",
        ),
        pytest.param(
            """
    class Entity:
        async def async_added_to_hass(self) -> None:
            x = 2

    class Child(Entity):
        async def async_added_to_hass(self) -> None:
            await Entity.async_added_to_hass()
    """,
            1,
            id="explicit_call_to_base_implementation",
        ),
        pytest.param(
            """
    class Entity:
        async def async_added_to_hass(self) -> None:
            \"\"\"\"\"\"

    class Coordinator:
        async def async_added_to_hass(self) -> None:
            x = 2

    class Child(Entity, Coordinator):
        async def async_added_to_hass(self) -> None:
            x = 3
    """,
            2,
            id="multiple_inheritance",
        ),
    ],
)
def test_enforce_super_call_bad(
    linter: UnittestLinter,
    hass_enforce_super_call: ModuleType,
    super_call_checker: BaseChecker,
    code: str,
    node_idx: int,
) -> None:
    """Bad test cases."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(super_call_checker)
    node = root_node.body[node_idx].body[0]

    with (
        patch.object(
            hass_enforce_super_call,
            "METHODS",
            new={"added_to_hass", "async_added_to_hass"},
        ),
        assert_adds_messages(
            linter,
            MessageTest(
                msg_id="hass-missing-super-call",
                node=node,
                line=node.lineno,
                args=(node.name,),
                col_offset=node.col_offset,
                end_line=node.position.end_lineno,
                end_col_offset=node.position.end_col_offset,
                confidence=INFERENCE,
            ),
        ),
    ):
        walker.walk(root_node)
