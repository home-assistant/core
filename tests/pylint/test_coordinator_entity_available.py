"""Tests for the coordinator entity available checker."""

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.coordinator_entity_available import (
    CoordinatorEntityAvailableChecker,
)
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

# Pre-load so astroid can resolve CoordinatorEntity in parsed snippets
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.update_coordinator")

_MODULE = "homeassistant.components.test_int.sensor"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> CoordinatorEntityAvailableChecker:
    """Fixture to provide a coordinator entity available checker."""
    return CoordinatorEntityAvailableChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return super().available and self.key in self.coordinator.data
""",
            _MODULE,
            id="super_available",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.device.online
""",
            _MODULE,
            id="last_update_success",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity, OtherEntity):
    @property
    def available(self) -> bool:
        return CoordinatorEntity.available.fget(self) and OtherEntity.available.fget(self)
""",
            _MODULE,
            id="coordinator_entity_available",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return True
""",
            _MODULE,
            id="always_available",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def native_value(self) -> int:
        return self.coordinator.data
""",
            _MODULE,
            id="no_override",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    @property
    def available(self) -> bool:
        return self.device.online
""",
            _MODULE,
            id="not_a_coordinator_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return self.device.online
""",
            "tests.components.test_int.test_sensor",
            id="not_an_integration_module",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: CoordinatorEntityAvailableChecker,
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

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return self.key in self.coordinator.data
""",
            id="coordinator_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyBaseEntity(CoordinatorEntity):
    pass

class MyEntity(MyBaseEntity):
    @property
    def available(self) -> bool:
        return self.device.online
""",
            id="indirect_coordinator_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return super()._attr_available and self.device.online
""",
            id="super_attr_available",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        if self.device is None:
            return False
        return True
""",
            id="not_always_available",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: CoordinatorEntityAvailableChecker,
    code: str,
) -> None:
    """Test cases that should trigger a warning."""
    root = astroid.parse(code, _MODULE)
    available = root.body[-1].locals["available"][0]

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-coordinator-entity-available",
            node=available,
            line=available.position.lineno,
            col_offset=available.position.col_offset,
            end_line=available.position.end_lineno,
            end_col_offset=available.position.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root)
