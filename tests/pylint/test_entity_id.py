"""Tests for the entity_id pylint checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.entity_id import HassEnforceEntityIdChecker
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> HassEnforceEntityIdChecker:
    """Fixture to provide the W7438 checker."""
    return HassEnforceEntityIdChecker(linter)


def _find_self_entity_id_target(root_node: nodes.Module) -> nodes.AssignAttr:
    """Return the first ``self.entity_id`` assignment target node."""
    for assign in root_node.nodes_of_class(
        (nodes.Assign, nodes.AnnAssign, nodes.AugAssign)
    ):
        targets = (
            list(assign.targets)
            if isinstance(assign, nodes.Assign)
            else [assign.target]
        )
        for target in targets:
            if (
                isinstance(target, nodes.AssignAttr)
                and target.attrname == "entity_id"
                and isinstance(target.expr, nodes.Name)
                and target.expr.name == "self"
            ):
                return target
    raise AssertionError("no self.entity_id assignment found")


def _expect(target: nodes.AssignAttr) -> MessageTest:
    """Build the expected MessageTest for a self.entity_id assignment."""
    return MessageTest(
        msg_id="home-assistant-entity-id",
        node=target,
        line=target.lineno,
        col_offset=target.col_offset,
        end_line=target.end_lineno,
        end_col_offset=target.end_col_offset,
    )


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, entity_id):
        self.entity_id = entity_id
""",
            id="init_plain_assign",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, entity_id):
        self.entity_id: str = entity_id
""",
            id="init_annotated_assign",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    async def async_added_to_hass(self):
        self.entity_id = f"sensor.{self._name}"
""",
            id="async_method_assign",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorEntity

class MySensor(SensorEntity):
    def __init__(self, entity_id):
        self.entity_id = entity_id
""",
            id="subclass_of_platform_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, entity_id):
        if entity_id:
            self.entity_id = entity_id
""",
            id="assign_inside_if_branch",
        ),
    ],
)
def test_entity_id_fires(
    linter: UnittestLinter,
    checker: HassEnforceEntityIdChecker,
    code: str,
) -> None:
    """W7438 fires when an entity class assigns to self.entity_id."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test.sensor")
    target_node = _find_self_entity_id_target(root_node)
    with assert_adds_messages(linter, _expect(target_node)):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, unique_id):
        self._attr_unique_id = unique_id
""",
            id="unique_id_instead",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, object_id):
        self._attr_suggested_object_id = object_id
""",
            id="suggested_object_id_instead",
        ),
        pytest.param(
            """
class NotAnEntity:
    def __init__(self, entity_id):
        self.entity_id = entity_id
""",
            id="non_entity_class",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, other):
        other.entity_id = "sensor.foo"
""",
            id="assign_on_other_object",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def read(self):
        return self.entity_id
""",
            id="read_only_access",
        ),
    ],
)
def test_entity_id_does_not_fire(
    linter: UnittestLinter,
    checker: HassEnforceEntityIdChecker,
    code: str,
) -> None:
    """W7438 does not fire for allowed patterns."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test.sensor")
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


def test_entity_id_not_flagged_outside_integration(
    linter: UnittestLinter,
    checker: HassEnforceEntityIdChecker,
) -> None:
    """W7438 does not fire outside integration modules."""
    root_node = astroid.parse(
        """
from homeassistant.helpers.entity import Entity

class MySensor(Entity):
    def __init__(self, entity_id):
        self.entity_id = entity_id
""",
        "homeassistant.helpers.entity_component",
    )
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)
