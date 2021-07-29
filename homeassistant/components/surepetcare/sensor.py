"""Support for Sure PetCare Flaps/Pets sensors."""
from __future__ import annotations

import logging

from surepy.entities import SurepyEntity
from surepy.entities.devices import Feeder as SureFeeder, FeederBowl as SureFeederBowl
from surepy.enums import EntityType

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_VOLTAGE,
    DEVICE_CLASS_BATTERY,
    MASS_GRAMS,
    PERCENTAGE,
)
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

        _LOGGER.debug(
            "🐾  setup - surepy_entity: %s (%s)", surepy_entity, surepy_entity.type.name
        )

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(SureBattery(surepy_entity.id, spc))
            _LOGGER.debug("🐾        - Battery: %s", surepy_entity)

        if surepy_entity.type == EntityType.FEEDER:

            for bowl in surepy_entity.bowls.values():
                entities.append(FeederBowl(surepy_entity.id, spc, bowl.raw_data()))
                _LOGGER.debug("🐾        - FeederBowl: %s", bowl)

            entities.append(Feeder(surepy_entity.id, spc))
            _LOGGER.debug("🐾        - Feeder: %s", surepy_entity)

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
        if surepy_entity.name:
            self._attr_name = f"{surepy_entity.type.name.capitalize()} {surepy_entity.name.capitalize()} Battery Level"
        else:
            self._attr_name = f"{surepy_entity.type.name.capitalize()}  Battery Level"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_unique_id = (
            f"{surepy_entity.household_id}-{surepy_entity.id}-battery"
        )

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self._name}"

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._surepy_entity.household_id}-{self._id}"

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return bool(self._state)

    @property
    def should_poll(self) -> bool:
        """Return true."""
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {**self._surepy_entity.raw_data()}

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
            self._attr_extra_state_attributes = None

        self.async_write_ha_state()

        _LOGGER.debug(
            "🐾  %s updated to: %s %s",
            surepy_entity.name,
            self._attr_state,
            self._attr_unit_of_measurement,
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, TOPIC_UPDATE, self._async_update)
        )
        self._async_update()


class FeederBowl(SensorEntity):
    """Sure Petcare Feeder Bowl."""

    _attr_should_poll = False

    def __init__(self, _id: int, spc: SurePetcareAPI, bowl_data: dict[str, int | str]):
        """Initialize a Sure Petcare Feeder-Bowl sensor."""

        self.feeder_id = _id
        self.bowl_id = int(bowl_data["index"])

        self._id = int(f"{_id}{str(self.bowl_id)}")
        self._spc: SurePetcareAPI = spc

        self._surepy_feeder_entity: SurepyEntity = self._spc.states[_id]
        self._surepy_entity: SureFeederBowl = self._spc.states[_id].bowls[self.bowl_id]
        self._state = bowl_data

        self._attr_name = (
            f"{EntityType.FEEDER.name.replace('_', ' ').title()} "
            f"{self._surepy_entity.name.capitalize()}"
        )
        self._attr_icon = "mdi:bowl"
        self._attr_available = bool(self._state)
        self._attr_unique_id = f"{self._surepy_feeder_entity.unique_id}-{self.bowl_id}"
        self._attr_unit_of_measurement = MASS_GRAMS

    @callback
    def _async_update(self) -> None:
        """Get the latest data and update the state."""

        self._state = self._surepy_entity.raw_data()
        self._attr_available = bool(self._state)
        self._attr_state = int(self._surepy_entity.weight)

        self.async_write_ha_state()

        _LOGGER.debug(
            "🐾  %s updated to: %s %s",
            self._surepy_entity.name,
            self._attr_state,
            self._attr_unit_of_measurement,
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, TOPIC_UPDATE, self._async_update)
        )
        self._async_update()


class Feeder(SensorEntity):
    """Sure Petcare Felaqua."""

    _attr_should_poll = False

    def __init__(self, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Feeder sensor."""

        super().__init__()

        self._id = _id
        self._spc = spc
        self._surepy_entity: SureFeeder = self._spc.states[self._id]

        self._attr_name = (
            f"{EntityType.FEEDER.name.replace('_', ' ').title()} "
            f"{self._surepy_entity.name.capitalize()}"
        )

        self._attr_unique_id = f"{self._surepy_entity.household_id}-{self._id}"
        self._attr_entity_picture = self._surepy_entity.icon
        self._attr_unit_of_measurement = MASS_GRAMS

    @callback
    def _async_update(self) -> None:
        """Get the latest data and update the state."""

        _LOGGER.debug("🐾  updating %s...", self._surepy_entity.name)

        self._state = self._surepy_entity.raw_data()["status"]

        _LOGGER.debug("🐾  self._state: %s", self._state)

        self._attr_state = int(self._surepy_entity.total_weight)
        self._attr_available = bool(self._attr_available)

        if lunch_data := self._surepy_entity.raw_data().get("lunch"):
            _LOGGER.debug("🐾  lunch_data: %s", lunch_data)
            for bowl_data in lunch_data["weights"]:
                self._surepy_entity.bowls[bowl_data["index"]]._data = bowl_data

        self.async_write_ha_state()

        _LOGGER.debug(
            "🐾  %s updated to: %s %s",
            self._surepy_entity.name,
            self._attr_state,
            self._attr_unit_of_measurement,
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, TOPIC_UPDATE, self._async_update)
        )
        self._async_update()
