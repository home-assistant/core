"""Binary sensor platform for Vevor Diesel Heater."""
from __future__ import annotations

PARALLEL_UPDATES = 1

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VevorHeaterConfigEntry
from .const import DOMAIN, ERROR_NONE, RUNNING_MODE_TEMPERATURE, RUNNING_STATE_ON
from .coordinator import VevorHeaterCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VevorHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vevor Heater binary sensors.

    Entities are created conditionally based on the detected BLE protocol.
    Mode 0 (unknown) creates all entities as safe fallback.
    """
    coordinator = entry.runtime_data
    mode = coordinator.protocol_mode

    # Core binary sensors (all protocols)
    entities: list[BinarySensorEntity] = [
        VevorHeaterActiveSensor(coordinator),
        VevorHeaterProblemSensor(coordinator),
        VevorHeaterConnectedSensor(coordinator),
    ]

    # Auto Start/Stop binary sensor (AA66Encrypted, ABBA, CBFF)
    if mode in (0, 4, 5, 6):
        entities.append(VevorAutoStartStopSensor(coordinator))

    async_add_entities(entities)


class VevorHeaterActiveSensor(
    CoordinatorEntity[VevorHeaterCoordinator], BinarySensorEntity
):
    """Vevor Heater active binary sensor."""

    _attr_has_entity_name = True
    _attr_name = "Active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_active"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def is_on(self) -> bool:
        """Return true if heater is running."""
        return self.coordinator.data.get("running_state") == RUNNING_STATE_ON

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorHeaterProblemSensor(
    CoordinatorEntity[VevorHeaterCoordinator], BinarySensorEntity
):
    """Vevor Heater problem binary sensor."""

    _attr_has_entity_name = True
    _attr_name = "Problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_problem"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def is_on(self) -> bool:
        """Return true if there's a problem."""
        return self.coordinator.data.get("error_code", 0) != ERROR_NONE

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorHeaterConnectedSensor(
    CoordinatorEntity[VevorHeaterCoordinator], BinarySensorEntity
):
    """Vevor Heater connected binary sensor."""

    _attr_has_entity_name = True
    _attr_name = "Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_registry_enabled_default = False  # Disabled by default

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_connected"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def is_on(self) -> bool:
        """Return true if connected."""
        return self.coordinator.data.get("connected", False)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorAutoStartStopSensor(
    CoordinatorEntity[VevorHeaterCoordinator], BinarySensorEntity
):
    """Vevor Heater Auto Start/Stop binary sensor.

    Shows whether Auto Start/Stop is enabled. When enabled in Temperature mode,
    the heater will completely stop when the room temperature reaches 2°C above
    the target, and restart when it drops 2°C below the target.
    """

    _attr_has_entity_name = True
    _attr_name = "Auto Start/Stop"
    _attr_icon = "mdi:thermostat-auto"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_auto_start_stop_sensor"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Auto Start/Stop is only relevant in Temperature mode.
        """
        if not self.coordinator.data.get("connected", False):
            return False
        return self.coordinator.data.get("running_mode") == RUNNING_MODE_TEMPERATURE

    @property
    def is_on(self) -> bool | None:
        """Return true if Auto Start/Stop is enabled."""
        return self.coordinator.data.get("auto_start_stop")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
