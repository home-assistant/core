"""Support for Sure PetCare Flaps/Pets sensors."""
from __future__ import annotations

import logging
from typing import Any

from surepy.entities import SurepyEntity
from surepy.entities.devices import Feeder as SureFeeder, FeederBowl as SureFeederBowl
from surepy.enums import EntityType, LockState

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_VOLTAGE,
    DEVICE_CLASS_BATTERY,
    MASS_GRAMS,
    PERCENTAGE,
    VOLUME_MILLILITERS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

# pylint: disable=relative-beyond-top-level
from . import SurePetcareAPI
from .const import DOMAIN, SPC, TOPIC_UPDATE

PARALLEL_UPDATES = 2


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: Any,
    discovery_info: Any = None,
) -> None:
    """Forward setup."""
    await async_setup_entry(hass, config, async_add_entities)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Any
) -> None:
    """Set up config entry Sure PetCare Flaps sensors."""

    entities: list[SurepyEntity] = []

    spc: SurePetcareAPI = hass.data[DOMAIN][SPC]

    for surepy_entity in spc.states.values():

        entity = None

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
        ]:
            entity = Flap(surepy_entity.id, spc)
            entities.append(entity)

        elif surepy_entity.type == EntityType.FELAQUA:
            entity = Felaqua(surepy_entity.id, spc)
            entities.append(entity)

        elif surepy_entity.type == EntityType.FEEDER:

            for bowl in surepy_entity.bowls.values():
                bowl_entity = FeederBowl(surepy_entity.id, spc, bowl.raw_data())
                entities.append(bowl_entity)

            entity = Feeder(surepy_entity.id, spc)
            entities.append(entity)

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entity = SureBattery(surepy_entity.id, spc)
            entities.append(entity)

        if entity:
            _LOGGER.debug("🐾 %s added...", entity.name)

    async_add_entities(entities)


class SurePetcareSensor(SensorEntity):  # type: ignore
    """A binary sensor implementation for Sure Petcare Entities."""

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

        return attributes

    @callback  # type: ignore
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
            self._attr_extra_state_attributes = {}
        self.async_write_ha_state()
        _LOGGER.debug("%s -> state: %s", self.name, state)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        self.async_on_remove(
            async_dispatcher_connect(self.hass, TOPIC_UPDATE, self._async_update)
        )

        @callback  # type: ignore
        def update() -> None:
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

        self._async_update()


class Flap(SurePetcareSensor):
    """Sure Petcare Flap."""

    @property
    def state(self) -> str:
        """Return battery level in percent."""
        return LockState(self._state["locking"]["mode"]).name.casefold()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {
                "learn_mode": bool(self._state["learn_mode"]),
                **self._surepy_entity.raw_data(),
            }

        return attributes

    @property
    def entity_picture(self) -> str | None:
        """Return the photo/icon."""
        return self._surepy_entity.icon


class Felaqua(SurePetcareSensor):
    """Sure Petcare Felaqua."""

    @property
    def state(self) -> int | None:
        """Return the remaining water."""
        self._surepy_entity: Felaqua
        return int(self._surepy_entity.water_remaining)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return str(VOLUME_MILLILITERS)

    @property
    def entity_picture(self) -> str | None:
        """Return the photo/icon."""
        return self._surepy_entity.icon

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None

        attrs: dict[str, Any] = self._surepy_entity.raw_data()
        weights: list[dict[str, int | float | str]] = attrs.get("drink", {}).get(
            "weights"
        )

        for weight in weights:
            attr_key = f"weight_{weight['index']}"
            attrs[attr_key] = weight

        attributes = attrs

        return attributes


class FeederBowl(SurePetcareSensor):
    """Sure Petcare Feeder Bowl."""

    def __init__(
        self, _id: int, spc: SurePetcareAPI, bowl_data: dict[str, int | str]
    ) -> None:
        """Initialize a Sure Petcare sensor."""

        super().__init__(_id, spc)

        self.feeder_id = _id
        self.bowl_id = int(bowl_data["index"])

        self._id = int(f"{_id}{str(self.bowl_id)}")
        self._spc: SurePetcareAPI = spc

        self._surepy_feeder_entity: SurepyEntity = self._spc.states[_id]
        self._surepy_entity: SureFeederBowl = self._spc.states[_id].bowls[
            self.bowl_id
        ]  # type:ignore
        self._state: dict[str, Any] = bowl_data

        # https://github.com/PyCQA/pylint/issues/2062
        # pylint: disable=no-member
        self._name = (
            f"{EntityType.FEEDER.name.replace('_', ' ').title()} "
            f"{self._surepy_entity.name.capitalize()}"
        )

    # @property
    # def name(self) -> str:
    #     """Return the name of the device if any."""
    #     return f"{self._name} "

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return (
            f"{self._surepy_feeder_entity.household_id}-{self.feeder_id}-{self.bowl_id}"
        )

    @property
    def state(self) -> int | None:
        """Return the remaining water."""
        return int(self._surepy_entity.weight)

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:bowl"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return str(MASS_GRAMS)

    @callback  # type: ignore
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        self._surepy_feeder_entity = self._spc.states[self.feeder_id]
        self._surepy_entity = self._spc.states[self.feeder_id].bowls[self.bowl_id]
        self._state = self._surepy_entity.raw_data()


class Feeder(SurePetcareSensor):
    """Sure Petcare Felaqua."""

    @property
    def state(self) -> int | None:
        """Return the total remaining food."""
        self._surepy_entity: SureFeeder
        return int(self._surepy_entity.total_weight)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return str(MASS_GRAMS)

    @property
    def entity_picture(self) -> str | None:
        """Return the photo url of the device."""
        return self._surepy_entity.icon

    @callback  # type: ignore
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        self._surepy_entity = self._spc.states[self._id]
        self._state = self._surepy_entity.raw_data()["status"]

        if lunch_data := self._surepy_entity.raw_data().get("lunch"):
            for bowl_data in lunch_data["weights"]:
                # requires library update, will be fixed when the library is updated
                # pylint: disable=protected-access
                self._surepy_entity.bowls[bowl_data["index"]]._data = bowl_data


class SureBattery(SurePetcareSensor):
    """Sure Petcare Flap."""

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self._name} Battery Level"

    @property
    def state(self) -> int | None:
        """Return battery level in percent."""
        return self._surepy_entity.battery_level

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._surepy_entity.household_id}-{self._surepy_entity.id}-battery"

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return str(DEVICE_CLASS_BATTERY)

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
        return str(PERCENTAGE)
