"""Number platform for Vevor Diesel Heater."""
from __future__ import annotations

PARALLEL_UPDATES = 1

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.const import EntityCategory, UnitOfVolume

from . import VevorHeaterConfigEntry
from .const import (
    DOMAIN,
    MAX_HEATER_OFFSET,
    MAX_LEVEL,
    MAX_TEMP_CELSIUS,
    MIN_HEATER_OFFSET,
    MIN_LEVEL,
    MIN_TEMP_CELSIUS,
)
from .coordinator import VevorHeaterCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VevorHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vevor Heater number entities.

    Entities are created conditionally based on the detected BLE protocol.
    Mode 0 (unknown) creates all entities as safe fallback.
    """
    coordinator = entry.runtime_data
    mode = coordinator.protocol_mode

    # Core number entities (all protocols)
    entities: list[NumberEntity] = [
        VevorHeaterLevelNumber(coordinator),
        VevorHeaterTemperatureNumber(coordinator),
        VevorTankCapacityNumber(coordinator),
    ]

    # Offset number (encrypted + CBFF protocols only)
    if mode in (0, 2, 4, 6):
        entities.append(VevorHeaterOffsetNumber(coordinator))

    async_add_entities(entities)


class VevorHeaterLevelNumber(CoordinatorEntity[VevorHeaterCoordinator], NumberEntity):
    """Vevor Heater level number entity."""

    _attr_has_entity_name = True
    _attr_name = "Level"
    _attr_icon = "mdi:gauge"
    _attr_native_min_value = MIN_LEVEL
    _attr_native_max_value = MAX_LEVEL
    _attr_native_step = 1

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_level"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.coordinator.data.get("set_level", MIN_LEVEL)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.coordinator.async_set_level(int(value))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorHeaterTemperatureNumber(
    CoordinatorEntity[VevorHeaterCoordinator], NumberEntity
):
    """Vevor Heater temperature number entity."""

    _attr_has_entity_name = True
    _attr_name = "Target Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"
    _attr_native_min_value = MIN_TEMP_CELSIUS
    _attr_native_max_value = MAX_TEMP_CELSIUS
    _attr_native_step = 1

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_target_temp"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        temp = self.coordinator.data.get("set_temp")
        return temp if temp is not None else MIN_TEMP_CELSIUS

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.coordinator.async_set_temperature(int(value))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorHeaterOffsetNumber(CoordinatorEntity[VevorHeaterCoordinator], NumberEntity):
    """Vevor Heater temperature offset number entity.

    This allows manual control of the temperature offset sent to the heater
    via BLE command 20. The heater uses this offset to adjust its internal
    temperature sensor reading for auto-start/stop logic.

    Both positive and negative offsets (-10 to +10) are supported.
    """

    _attr_has_entity_name = True
    _attr_name = "Temperature Offset"
    _attr_icon = "mdi:thermometer-plus"
    _attr_native_unit_of_measurement = "°C"
    _attr_native_min_value = MIN_HEATER_OFFSET
    _attr_native_max_value = MAX_HEATER_OFFSET
    _attr_native_step = 1
    _attr_entity_category = None  # Show in main controls, not configuration

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_heater_offset"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.coordinator.data.get("heater_offset", 0)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.coordinator.async_set_heater_offset(int(value))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorTankCapacityNumber(CoordinatorEntity[VevorHeaterCoordinator], NumberEntity):
    """Tank capacity number entity for estimated fuel tracking.

    Allows the user to set their actual tank capacity in liters (1-100L).
    This is independent from the heater's BLE Tank Volume setting and is
    used locally to calculate the estimated fuel remaining.
    """

    _attr_has_entity_name = True
    _attr_name = "Tank Capacity"
    _attr_icon = "mdi:gas-station"
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_tank_capacity"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.coordinator.data.get("tank_capacity")

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.coordinator.async_set_tank_capacity(int(value))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


