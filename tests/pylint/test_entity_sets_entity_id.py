"""Tests for the entity_id pylint checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.entity_id import HassEntitySetsEntityIdChecker
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

_MSG_ID = "home-assistant-entity-sets-entity-id"
_MODULE = "homeassistant.components.test_integration.sensor"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> HassEntitySetsEntityIdChecker:
    """Fixture to provide the W7461 checker."""
    return HassEntitySetsEntityIdChecker(linter)


def _assigned_node(root_node: nodes.Module) -> nodes.AssignName | nodes.AssignAttr:
    """Return the single ``entity_id`` assignment target in the module."""
    targets = [
        node
        for node in root_node.nodes_of_class((nodes.AssignName, nodes.AssignAttr))
        if getattr(node, "name", None) == "entity_id"
        or getattr(node, "attrname", None) == "entity_id"
    ]
    assert len(targets) == 1
    return targets[0]


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    entity_id = "sensor.my_entity"
""",
            id="class_body",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    entity_id: str = "sensor.my_entity"
""",
            id="class_body_annotated",
        ),
        pytest.param(
            """
from homeassistant.components.sensor import SensorEntity

class MyEntity(SensorEntity):
    def __init__(self, key: str) -> None:
        self.entity_id = f"sensor.{key}"
""",
            id="init",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    async def async_added_to_hass(self) -> None:
        if True:
            self.entity_id = "sensor.my_entity"
""",
            id="nested_block",
        ),
    ],
)
def test_entity_sets_entity_id(
    linter: UnittestLinter, checker: HassEntitySetsEntityIdChecker, code: str
) -> None:
    """Test entities assigning their own entity_id are flagged."""
    root_node = astroid.parse(code, _MODULE)
    node = _assigned_node(root_node)
    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id=_MSG_ID,
            node=node,
            line=node.lineno,
            col_offset=node.col_offset,
            end_line=node.end_lineno,
            end_col_offset=node.end_col_offset,
            args=("MyEntity",),
        ),
    ):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    entity_id: str
""",
            _MODULE,
            id="annotation_only",
        ),
        pytest.param(
            """
class NotAnEntity:
    entity_id = "sensor.my_entity"

    def __init__(self, entity_id: str) -> None:
        self.entity_id = entity_id
""",
            _MODULE,
            id="not_an_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self, other) -> None:
        other.entity_id = "sensor.my_entity"
        entity_id = "sensor.my_entity"
""",
            _MODULE,
            id="not_self",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def __init__(self) -> None:
        self.entity_id = "sensor.my_entity"
""",
            "homeassistant.helpers.test",
            id="not_integration_module",
        ),
    ],
)
def test_entity_sets_entity_id_not_flagged(
    linter: UnittestLinter,
    checker: HassEntitySetsEntityIdChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not be flagged."""
    root_node = astroid.parse(code, module_name)
    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)
