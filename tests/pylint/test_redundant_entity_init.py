"""Tests for the redundant_entity_init pylint checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.redundant_entity_init import (
    RedundantEntityInitChecker,
)
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

# Pre-load the entity modules so astroid can resolve the base classes in
# the parsed snippets instead of depending on component-level imports.
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.entity")
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.update_coordinator")

_MODULE = "homeassistant.components.pylint_test.sensor"

_ENTITY_IMPORT = "from homeassistant.helpers.entity import Entity"

_BASE_ENTITY = f"""
{_ENTITY_IMPORT}

class MyBaseEntity(Entity):
    def __init__(self, name: str, option: int) -> None:
        \"\"\"Initialize.\"\"\"
        self._attr_name = name
        self.option = option
"""
_COORDINATOR_IMPORT = """
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

class MyCoordinator(DataUpdateCoordinator[dict]):
    \"\"\"Coordinator.\"\"\"

class MyDescription:
    \"\"\"Description.\"\"\"
"""


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> RedundantEntityInitChecker:
    """Fixture to provide the R7405 checker."""
    return RedundantEntityInitChecker(linter)


def _init_node(root_node: nodes.Module, class_name: str) -> nodes.FunctionDef:
    """Return the ``__init__`` FunctionDef of the named class."""
    class_node = next(
        node
        for node in root_node.nodes_of_class(nodes.ClassDef)
        if node.name == class_name
    )
    return next(
        node
        for node in class_node.body
        if isinstance(node, nodes.FunctionDef) and node.name == "__init__"
    )


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name)
        self._attr_unique_id = name
            """,
            id="extra_statement",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name.lower())
            """,
            id="modified_argument",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, first: str, second: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(second, first)
            """,
            id="reordered_arguments",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, first: str, second: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(first)
            """,
            id="dropped_parameter",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name, extra=1)
            """,
            id="extra_argument",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, name: str, *, option: int) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name, other=option)
            """,
            id="renamed_keyword",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, name: str = "default") -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name)
            """,
            id="parameter_with_default",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, *, name: str = "default") -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name=name)
            """,
            id="keyword_only_with_default",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        super(MyEntity, self).__init__(name)
            """,
            id="explicit_super_arguments",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        Entity.__init__(self, name)
            """,
            id="explicit_base_call",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().added_to_hass(name)
            """,
            id="other_super_method",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, *args, **kwargs) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(*args)
            """,
            id="dropped_double_star",
        ),
        pytest.param(
            f"""
from dataclasses import dataclass

{_ENTITY_IMPORT}

@dataclass
class MyEntity(Entity):
    _attr_native_step: float = 1

    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name)
            """,
            id="dataclass_decorated_class",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}
from typing import Any

class MyWeatherMixin(Entity):
    def __init__(self, device: str, **kwargs: Any) -> None:
        \"\"\"Initialize.\"\"\"
        self._attr_name = device

class MySensor(MyWeatherMixin):
    def __init__(self, netatmo_device: str, description: object) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(netatmo_device, description=description)
            """,
            id="parent_absorbs_parameter_into_kwargs",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyBaseEntity(Entity):
    def __init__(self, first: str, second: int) -> None:
        \"\"\"Initialize.\"\"\"
        self._attr_name = first

class MySensor(MyBaseEntity):
    def __init__(self, second: int, first: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(first=first, second=second)
            """,
            id="parent_declares_parameters_in_another_order",
        ),
        pytest.param(
            """
class NotAnEntity:
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name)
            """,
            id="not_an_entity",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

def __init__(self, name: str) -> None:
    \"\"\"Initialize.\"\"\"
    super().__init__(name)
            """,
            id="not_a_method",
        ),
    ],
)
def test_redundant_entity_init_good(
    linter: UnittestLinter,
    checker: RedundantEntityInitChecker,
    code: str,
) -> None:
    """Constructors that do something of their own are not flagged."""
    root_node = astroid.parse(code, _MODULE)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


def test_redundant_entity_init_outside_integration(
    linter: UnittestLinter,
    checker: RedundantEntityInitChecker,
) -> None:
    """A pure delegation outside an integration module is not flagged."""
    root_node = astroid.parse(
        f"""
{_ENTITY_IMPORT}

class MyEntity(Entity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name)
        """,
        "tests.components.pylint_test.test_sensor",
    )

    with assert_no_messages(linter):
        walk_checker(linter, checker, root_node)


@pytest.mark.parametrize(
    ("code", "class_name"),
    [
        pytest.param(
            f"""
{_COORDINATOR_IMPORT}

class MyBaseEntity(CoordinatorEntity[MyCoordinator]):
    def __init__(
        self,
        coordinator: MyCoordinator,
        machine: str,
        description: object,
    ) -> None:
        \"\"\"Initialize the entity.\"\"\"
        super().__init__(coordinator)
        self.machine = machine

class MySensor(MyBaseEntity):
    def __init__(
        self,
        coordinator: MyCoordinator,
        machine: str,
        description: MyDescription,
    ) -> None:
        \"\"\"Initialize the sensor.\"\"\"
        super().__init__(coordinator, machine, description)
            """,
            "MySensor",
            id="narrowed_annotations",
        ),
        pytest.param(
            f"""
{_BASE_ENTITY}

class MySensor(MyBaseEntity):
    def __init__(self, name: str, option: int) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name, option)
            """,
            "MySensor",
            id="forwarded_positionally",
        ),
        pytest.param(
            f"""
{_BASE_ENTITY}

class MySensor(MyBaseEntity):
    def __init__(self, name: str, option: int) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name=name, option=option)
            """,
            "MySensor",
            id="forwarded_by_keyword",
        ),
        pytest.param(
            f"""
{_BASE_ENTITY}

class MySensor(MyBaseEntity):
    def __init__(self, *args, **kwargs) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(*args, **kwargs)
            """,
            "MySensor",
            id="star_args",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyBaseEntity(Entity):
    def __init__(self, name: str, option: int = 1) -> None:
        \"\"\"Initialize.\"\"\"
        self._attr_name = name

class MySensor(MyBaseEntity):
    def __init__(self, name: str) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name)
            """,
            "MySensor",
            id="parent_has_extra_optional_parameter",
        ),
        pytest.param(
            f"""
{_ENTITY_IMPORT}

class MyBaseEntity(Entity):
    def __init__(self, name: str, *, option: int) -> None:
        \"\"\"Initialize.\"\"\"
        self._attr_name = name

class MySensor(MyBaseEntity):
    def __init__(self, name: str, *, option: int) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name, option=option)
            """,
            "MySensor",
            id="keyword_only_parameter",
        ),
        pytest.param(
            f"""
{_BASE_ENTITY}

class MySensor(MyBaseEntity):
    def __init__(self, name: str, /, option: int) -> None:
        \"\"\"Initialize.\"\"\"
        super().__init__(name, option)
            """,
            "MySensor",
            id="positional_only_parameter",
        ),
        pytest.param(
            f"""
{_BASE_ENTITY}

class MySensor(MyBaseEntity):
    def __init__(self, name: str, option: int) -> None:
        super().__init__(name, option)
            """,
            "MySensor",
            id="no_docstring",
        ),
    ],
)
def test_redundant_entity_init_bad(
    linter: UnittestLinter,
    checker: RedundantEntityInitChecker,
    code: str,
    class_name: str,
) -> None:
    """Pure delegation constructors are flagged."""
    root_node = astroid.parse(code, _MODULE)
    node = _init_node(root_node, class_name)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-redundant-entity-init",
            node=node,
            line=node.lineno,
            args=(class_name,),
            col_offset=node.col_offset,
            end_line=node.position.end_lineno,
            end_col_offset=node.position.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root_node)
