"""Support for Sure PetCare Flaps/Pets sensors."""
from __future__ import annotations

import logging

from surepy.entities import SurepyEntity
from surepy.enums import EntityType

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_VOLTAGE, DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SurePetcareDataCoordinator
from .const import DOMAIN, SURE_BATT_VOLTAGE_DIFF, SURE_BATT_VOLTAGE_LOW
from .entity import SurePetcareEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sure PetCare Flaps sensors."""

    entities: list[SureBattery] = []

    coordinator: SurePetcareDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    for surepy_entity in coordinator.data.values():

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(SureBattery(surepy_entity.id, coordinator))

    async_add_entities(entities)


class SureBattery(SurePetcareEntity, SensorEntity):
    """A sensor implementation for Sure Petcare Entities."""

    _attr_device_class = DEVICE_CLASS_BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, surepetcare_id: int, coordinator: SurePetcareDataCoordinator
    ) -> None:
        """Initialize a Sure Petcare battery sensor."""
        super().__init__(surepetcare_id, coordinator)

        self._attr_name = f"{self._device_name} Battery Level"
        self._attr_unique_id = f"{self._device_id}-battery"

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        """Update the state and attributes."""
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
