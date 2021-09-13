"""Support for Sure PetCare Flaps/Pets sensors."""
from __future__ import annotations

import logging

from surepy.entities import SurepyEntity
from surepy.enums import EntityType

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_VOLTAGE, DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, SURE_BATT_VOLTAGE_DIFF, SURE_BATT_VOLTAGE_LOW

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Sure PetCare Flaps sensors."""

    entities: list[SurepyEntity] = []

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    for surepy_entity in coordinator.data.values():

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(SureBattery(surepy_entity.id, coordinator))

    async_add_entities(entities)


class SureBattery(CoordinatorEntity, SensorEntity):
    """A sensor implementation for Sure Petcare Entities."""

    def __init__(self, _id: int, coordinator: DataUpdateCoordinator) -> None:
        """Initialize a Sure Petcare sensor."""
        super().__init__(coordinator)

        self._id = _id

        surepy_entity: SurepyEntity = coordinator.data[_id]

        self._attr_device_class = DEVICE_CLASS_BATTERY
        if surepy_entity.name:
            self._attr_name = f"{surepy_entity.type.name.capitalize()} {surepy_entity.name.capitalize()} Battery Level"
        else:
            self._attr_name = f"{surepy_entity.type.name.capitalize()}  Battery Level"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_unique_id = (
            f"{surepy_entity.household_id}-{surepy_entity.id}-battery"
        )
        self._update_attr()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and update the state."""
        self._update_attr()
        self.async_write_ha_state()

    @callback
    def _update_attr(self) -> None:
        """Update the state and attributes."""
        surepy_entity = self.coordinator.data[self._id]
        state = surepy_entity.raw_data()["status"]

        try:
            per_battery_voltage = state["battery"] / 4
            voltage_diff = per_battery_voltage - SURE_BATT_VOLTAGE_LOW
            self._attr_native_value = min(
                int(voltage_diff / SURE_BATT_VOLTAGE_DIFF * 100), 100
            )
        except (KeyError, TypeError):
            self._attr_native_value = None

        if state:
            voltage_per_battery = float(state["battery"]) / 4
            self._attr_extra_state_attributes = {
                ATTR_VOLTAGE: f"{float(state['battery']):.2f}",
                f"{ATTR_VOLTAGE}_per_battery": f"{voltage_per_battery:.2f}",
            }
        else:
            self._attr_extra_state_attributes = {}
        _LOGGER.debug("%s -> state: %s", self.name, state)
