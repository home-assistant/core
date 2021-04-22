"""Support for Sure PetCare Flaps/Pets sensors."""
from __future__ import annotations

import logging
from typing import Any

from surepy.entities import SurepyEntity
from surepy.enums import EntityType, LockState

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

    # for entity in spc.ids:
    for surepy_entity in spc.states.values():

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(SureBattery(surepy_entity.id, spc))

    async_add_entities(entities, True)


class SurePetcareSensor(SensorEntity):
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(self, _id: int, spc: SurePetcareAPI):
        """Initialize a Sure Petcare sensor."""

        self._id = _id
        self._spc: SurePetcareAPI = spc

        self._surepy_entity: SurepyEntity = self._spc.states[_id]
        self._state: dict[str, Any] = {}
        self._name = (
            f"{self._surepy_entity.type.name.capitalize()} "
            f"{self._surepy_entity.name.capitalize()}"
        )

        self._async_unsub_dispatcher_connect = None

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._surepy_entity.household_id}-{self._surepy_entity.id}"

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return bool(self._state)

    @property
    def should_poll(self) -> bool:
        """Return true."""
        return False

    async def async_update(self) -> None:
        """Get the latest data and update the state."""
        self._surepy_entity = self._spc.states[self._id]
        self._state = self._surepy_entity.raw_data()["status"]
        _LOGGER.debug("%s -> self._state: %s", self._name, self._state)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def update() -> None:
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()


class Flap(SurePetcareSensor):
    """Sure Petcare Flap."""

    @property
    def state(self) -> int | None:
        """Return battery level in percent."""
        return LockState(self._state["locking"]["mode"]).name.capitalize()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {"learn_mode": bool(self._state["learn_mode"])}

        return attributes


class SureBattery(SurePetcareSensor):
    """Sure Petcare Flap."""

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self._name} Battery Level"

    @property
    def state(self) -> int | None:
        """Return battery level in percent."""
        battery_percent: int | None
        try:
            per_battery_voltage = self._state["battery"] / 4
            voltage_diff = per_battery_voltage - SURE_BATT_VOLTAGE_LOW
            battery_percent = min(int(voltage_diff / SURE_BATT_VOLTAGE_DIFF * 100), 100)
        except (KeyError, TypeError):
            battery_percent = None

        return battery_percent

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._surepy_entity.household_id}-{self._surepy_entity.id}-battery"

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return DEVICE_CLASS_BATTERY

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        attributes = None
        if self._state:
            voltage_per_battery = float(self._state["battery"]) / 4
            attributes = {
                ATTR_VOLTAGE: f"{float(self._state['battery']):.2f}",
                f"{ATTR_VOLTAGE}_per_battery": f"{voltage_per_battery:.2f}",
            }

        return attributes

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return PERCENTAGE
