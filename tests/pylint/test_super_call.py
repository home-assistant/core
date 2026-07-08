"""Tests for pylint hass_enforce_super_call plugin."""

from unittest.mock import patch

import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import INFERENCE
from pylint.testutils import MessageTest
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
    class Entity:
        async def async_added_to_hass(self) -> None:
            pass
    """,
            id="added_to_no_parent",
        ),
        pytest.param(
            """
    class Entity:
        async def async_will_remove_from_hass(self) -> None:
            pass
    """,
            id="will_remove_from_no_parent",
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
            id="added_to_empty_parent_implementation",
        ),
        pytest.param(
            """
    class Entity:
        async def async_will_remove_from_hass(self) -> None:
            \"\"\"Some docstring.\"\"\"

    class Child(Entity):
        async def async_will_remove_from_hass(self) -> None:
            x = 2
        """,
            id="will_remove_from_empty_parent_implementation",
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
            id="added_to_empty_parent_implementation2",
        ),
        pytest.param(
            """
    class Entity:
        async def async_will_remove_from_hass(self) -> None:
            \"\"\"Some docstring.\"\"\"
            pass

    class Child(Entity):
        async def async_will_remove_from_hass(self) -> None:
            x = 2
        """,
            id="will_remove_from_empty_parent_implementation2",
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
            id="added_to_correct_super_call",
        ),
        pytest.param(
            """
    class Entity:
        async def async_will_remove_from_hass(self) -> None:
            x = 2

    class Child(Entity):
        async def async_will_remove_from_hass(self) -> None:
            await super().async_will_remove_from_hass()
        """,
            id="will_remove_from_correct_super_call",
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
            id="added_to_super_call_in_return",
        ),
        pytest.param(
            """
    class Entity:
        async def async_will_remove_from_hass(self) -> None:
            x = 2

    class Child(Entity):
        async def async_will_remove_from_hass(self) -> None:
            return await super().async_will_remove_from_hass()
        """,
            id="will_remove_from_super_call_in_return",
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
            id="added_to_super_call_not_async",
        ),
        pytest.param(
            """
    class Entity:
        def async_will_remove_from_hass(self) -> None:
            x = 2

    class Child(Entity):
        def async_will_remove_from_hass(self) -> None:
            super().async_will_remove_from_hass()
        """,
            id="will_remove_from_super_call_not_async",
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
            id="added_to_multiple_inheritance",
        ),
        pytest.param(
            """
    class Entity:
        async def async_will_remove_from_hass(self) -> None:
            \"\"\"\"\"\"

    class Coordinator:
        async def async_will_remove_from_hass(self) -> None:
            x = 2

    class Child(Entity, Coordinator):
        async def async_will_remove_from_hass(self) -> None:
            await super().async_will_remove_from_hass()
        """,
            id="will_remove_from_multiple_inheritance",
        ),
        pytest.param(
            """
        async def async_added_to_hass() -> None:
            x = 2
        """,
            id="added_to_not_a_method",
        ),
        pytest.param(
            """
        async def async_will_remove_from_hass() -> None:
            x = 2
        """,
            id="will_remove_from_not_a_method",
        ),
    ],
)
def test_enforce_super_call(
    linter: UnittestLinter,
    super_call_checker: BaseChecker,
    code: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")

    with (
        patch(
            "pylint_home_assistant.checkers.super_call.METHODS",
            new={
                "added_to_hass",
                "async_added_to_hass",
                "will_remove_from_hass",
                "async_will_remove_from_hass",
            },
        ),
        assert_no_messages(linter),
    ):
        walk_checker(linter, super_call_checker, root_node)


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
            id="added_to_no_super_call",
        ),
        pytest.param(
            """
    class Entity:
        def async_will_remove_from_hass(self) -> None:
            x = 2

    class Child(Entity):
        def async_will_remove_from_hass(self) -> None:
            x = 3
    """,
            1,
            id="will_remove_from_no_super_call",
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
            id="added_to_no_super_call",
        ),
        pytest.param(
            """
    class Entity:
        async def async_will_remove_from_hass(self) -> None:
            x = 2

    class Child(Entity):
        async def async_will_remove_from_hass(self) -> None:
            x = 3
    """,
            1,
            id="will_remove_from_no_super_call",
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
            id="added_to_explicit_call_to_base_implementation",
        ),
        pytest.param(
            """
    class Entity:
        async def async_will_remove_from_hass(self) -> None:
            x = 2

    class Child(Entity):
        async def async_will_remove_from_hass(self) -> None:
            await Entity.async_will_remove_from_hass()
    """,
            1,
            id="will_remove_from_explicit_call_to_base_implementation",
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
            id="added_to_multiple_inheritance",
        ),
        pytest.param(
            """
    class Entity:
        async def async_will_remove_from_hass(self) -> None:
            \"\"\"\"\"\"

    class Coordinator:
        async def async_will_remove_from_hass(self) -> None:
            x = 2

    class Child(Entity, Coordinator):
        async def async_will_remove_from_hass(self) -> None:
            x = 3
    """,
            2,
            id="will_remove_from_multiple_inheritance",
        ),
    ],
)
def test_enforce_super_call_bad(
    linter: UnittestLinter,
    super_call_checker: BaseChecker,
    code: str,
    node_idx: int,
) -> None:
    """Bad test cases."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    node = root_node.body[node_idx].body[0]

    with (
        patch(
            "pylint_home_assistant.checkers.super_call.METHODS",
            new={
                "added_to_hass",
                "async_added_to_hass",
                "will_remove_from_hass",
                "async_will_remove_from_hass",
            },
        ),
        assert_adds_messages(
            linter,
            MessageTest(
                msg_id="home-assistant-missing-super-call",
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
        walk_checker(linter, super_call_checker, root_node)
