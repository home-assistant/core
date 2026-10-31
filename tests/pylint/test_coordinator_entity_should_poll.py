"""Tests for the coordinator entity should_poll checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.coordinator_entity_should_poll import (
    CoordinatorEntityShouldPollChecker,
)
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

# Pre-load so astroid can resolve the entity classes in parsed snippets
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.update_coordinator")

_MODULE = "homeassistant.components.test_int.sensor"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> CoordinatorEntityShouldPollChecker:
    """Fixture to provide a coordinator entity should_poll checker."""
    return CoordinatorEntityShouldPollChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity[MyCoordinator]):
    _attr_has_entity_name = True
""",
            _MODULE,
            id="no_should_poll",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    _attr_should_poll = False
""",
            _MODULE,
            id="not_a_coordinator_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity[MyCoordinator]):
    _attr_should_poll = True

    @property
    def should_poll(self) -> bool:
        return self._attr_should_poll
""",
            _MODULE,
            id="should_poll_overridden",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class PollingMixin(Entity):
    @property
    def should_poll(self) -> bool:
        return self._attr_should_poll

class MyEntity(PollingMixin, CoordinatorEntity[MyCoordinator]):
    _attr_should_poll = True
""",
            _MODULE,
            id="should_poll_overridden_by_mixin",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity[MyCoordinator]):
    _attr_should_poll = False
""",
            "homeassistant.helpers.my_helper",
            id="not_an_integration",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: CoordinatorEntityShouldPollChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity[MyCoordinator]):
    _attr_should_poll = False
""",
            id="class_attribute",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity[MyCoordinator]):
    _attr_should_poll: bool = False
""",
            id="annotated_class_attribute",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity[MyCoordinator]):
    def __init__(self, coordinator: MyCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_should_poll = True
""",
            id="instance_attribute",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyBaseEntity(CoordinatorEntity[MyCoordinator]):
    pass

class MyEntity(MyBaseEntity):
    _attr_should_poll = False
""",
            id="integration_base_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyMixin(Entity):
    pass

class MyEntity(MyMixin, CoordinatorEntity[MyCoordinator]):
    _attr_should_poll = False
""",
            id="mixin_first",
        ),
    ],
)
def test_should_poll(
    linter: UnittestLinter,
    checker: CoordinatorEntityShouldPollChecker,
    code: str,
) -> None:
    """Test setting _attr_should_poll on a coordinator entity is flagged."""
    root = astroid.parse(code, _MODULE)
    assignment = next(
        node
        for node in root.nodes_of_class((nodes.Assign, nodes.AnnAssign))
        if "_attr_should_poll" in node.as_string()
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-coordinator-entity-should-poll",
            node=assignment,
            line=assignment.lineno,
            col_offset=assignment.col_offset,
            end_line=assignment.end_lineno,
            end_col_offset=assignment.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root)
