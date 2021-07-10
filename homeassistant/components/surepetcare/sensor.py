"""Support for Sure PetCare Flaps/Pets sensors."""
from __future__ import annotations

import logging

from surepy.entities import SurepyEntity
from surepy.enums import EntityType

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_VOLTAGE, DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import SurePetcareAPI
from .const import (
    DOMAIN,
    SPC,
    SURE_BATT_VOLTAGE_DIFF,
    SURE_BATT_VOLTAGE_LOW,
    TOPIC_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Sure PetCare Flaps sensors."""
    if discovery_info is None:
        return

    entities: list[SurepyEntity] = []

    spc: SurePetcareAPI = hass.data[DOMAIN][SPC]

    for surepy_entity in spc.states.values():

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(SureBattery(surepy_entity.id, spc))

    async_add_entities(entities)


class SureBattery(SensorEntity):
    """A sensor implementation for Sure Petcare Entities."""

    _attr_should_poll = False

    def __init__(self, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare sensor."""

        self._id = _id
        self._spc: SurePetcareAPI = spc

        surepy_entity: SurepyEntity = self._spc.states[_id]

        self._attr_device_class = DEVICE_CLASS_BATTERY
        self._attr_name = f"{surepy_entity.type.name.capitalize()} {surepy_entity.name.capitalize()} Battery Level"
        self._attr_unit_of_measurement = PERCENTAGE
        self._attr_unique_id = (
            f"{surepy_entity.household_id}-{surepy_entity.id}-battery"
        )

    @callback
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        surepy_entity = self._spc.states[self._id]
        state = surepy_entity.raw_data()["status"]

        self._attr_available = bool(state)
        try:
            per_battery_voltage = state["battery"] / 4
            voltage_diff = per_battery_voltage - SURE_BATT_VOLTAGE_LOW
            self._attr_state = min(
                int(voltage_diff / SURE_BATT_VOLTAGE_DIFF * 100), 100
            )
        except (KeyError, TypeError):
            self._attr_state = None

        if state:
            voltage_per_battery = float(state["battery"]) / 4
            self._attr_extra_state_attributes = {
                ATTR_VOLTAGE: f"{float(state['battery']):.2f}",
                f"{ATTR_VOLTAGE}_per_battery": f"{voltage_per_battery:.2f}",
            }
        else:
            self._attr_extra_state_attributes = None
        self.async_write_ha_state()
        _LOGGER.debug("%s -> state: %s", self.name, state)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, TOPIC_UPDATE, self._async_update)
        )
        self._async_update()
