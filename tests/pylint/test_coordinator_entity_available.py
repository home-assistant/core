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
    def available(self) -> bool:
        def check():
            return self.device.online
        return True
""",
            _MODULE,
            id="always_available_nested_function",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, config_entry) -> None:
        super().__init__(hass, LOGGER, config_entry=config_entry, name="test")

class MyEntity(CoordinatorEntity[MyCoordinator]):
    @property
    def available(self) -> bool:
        return self.key in self.coordinator.data
""",
            _MODULE,
            id="push_coordinator",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, config_entry) -> None:
        super().__init__(
            hass, LOGGER, config_entry=config_entry, name="test", update_interval=None
        )

class MyBaseCoordinator(MyCoordinator):
    pass

class MyBaseEntity(CoordinatorEntity["MyBaseCoordinator"]):
    pass

class MyEntity(MyBaseEntity):
    @property
    def available(self) -> bool:
        return self.key in self.coordinator.data
""",
            _MODULE,
            id="push_coordinator_forward_reference",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return self.device.online
""",
            _MODULE,
            id="own_source",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return self.websocket_alive and self.key in self.coordinator.data
""",
            _MODULE,
            id="own_source_and_coordinator_data",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        if self.device.connected:
            return self.key in self.coordinator.data
        return False
""",
            _MODULE,
            id="own_source_in_condition",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return self._attr_available and self.key in self.coordinator.data
""",
            _MODULE,
            id="attr_available",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return self.coordinator.client.is_available
""",
            _MODULE,
            id="coordinator_attribute",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return self.entity_description.available_fn(self.coordinator)
""",
            _MODULE,
            id="coordinator_passed_on",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    def _vehicle(self):
        if not super().available:
            return None
        return self.coordinator.data.get(self.key)

    @property
    def available(self) -> bool:
        return self._vehicle() is not None
""",
            _MODULE,
            id="super_available_in_helper",
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

class MyEntity(CoordinatorEntity):
    @property
    def data(self) -> dict | None:
        return self.coordinator.data.get(self.key)

    @property
    def available(self) -> bool:
        return self.data is not None
""",
            id="entity_property",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

class MyCoordinator(DataUpdateCoordinator[dict]):
    def get_device(self, key: str) -> dict | None:
        return self.data.get(key)

class MyEntity(CoordinatorEntity[MyCoordinator]):
    @property
    def available(self) -> bool:
        return self.coordinator.get_device(self.key) is not None
""",
            id="coordinator_method",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return self.entity_description.available_fn(self.coordinator.data)
""",
            id="description_callable",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return self.coordinator.data[self.device.mac]["available"]
""",
            id="own_attribute_as_key",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def _device(self) -> dict | None:
        if self._has_device:
            return self.coordinator.data.get(self.key)
        return None

    @property
    def _has_device(self) -> bool:
        return self._device is not None or self.key in self.coordinator.data

    @property
    def available(self) -> bool:
        return self._device is not None
""",
            id="recursive_properties",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return is_present(self.hass, self.coordinator.data["address"])
""",
            id="hass_argument",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyBaseEntity(CoordinatorEntity):
    pass

class MyEntity(MyBaseEntity):
    @property
    def available(self) -> bool:
        return self.key in self.coordinator.data
""",
            id="indirect_coordinator_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        return super()._attr_available and self.key in self.coordinator.data
""",
            id="super_attr_available",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        if self.coordinator.data is None:
            return False
        return True
""",
            id="not_always_available",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def available(self) -> bool:
        if self.coordinator.data is not None:
            return True
""",
            id="conditional_true_falls_through",
        ),
        pytest.param(
            """
from datetime import timedelta

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, config_entry) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="test",
            update_interval=timedelta(minutes=1),
        )

class MyEntity(CoordinatorEntity[MyCoordinator]):
    @property
    def available(self) -> bool:
        return self.key in self.coordinator.data
""",
            id="polling_coordinator",
        ),
        pytest.param(
            """
from datetime import timedelta

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, config_entry) -> None:
        super().__init__(hass, LOGGER, config_entry=config_entry, name="test")

    async def _async_setup(self) -> None:
        self.update_interval = timedelta(minutes=1)

class MyEntity(CoordinatorEntity[MyCoordinator]):
    @property
    def available(self) -> bool:
        return self.key in self.coordinator.data
""",
            id="interval_set_later",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

class MyCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, **kwargs) -> None:
        super().__init__(hass, LOGGER, **kwargs)

class MyEntity(CoordinatorEntity[MyCoordinator]):
    @property
    def available(self) -> bool:
        return self.key in self.coordinator.data
""",
            id="interval_in_kwargs",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

class MyCoordinator(DataUpdateCoordinator[dict]):
    pass

class MyEntity(CoordinatorEntity[MyCoordinator]):
    @property
    def available(self) -> bool:
        return self.key in self.coordinator.data
""",
            id="coordinator_without_init",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity[UnknownCoordinator]):
    @property
    def available(self) -> bool:
        return self.key in self.coordinator.data
""",
            id="unknown_coordinator",
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
