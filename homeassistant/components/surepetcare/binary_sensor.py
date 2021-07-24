"""Support for Sure PetCare Flaps/Pets binary sensors."""
from __future__ import annotations

import logging
from typing import Any

from surepy.entities import PetLocation, SurepyEntity
from surepy.entities.pet import Pet as SurePet
from surepy.enums import EntityType, Location

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PRESENCE,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    """Set up Sure PetCare Flaps binary sensors based on a config entry."""
    if discovery_info is None:
        return

    entities: list[SurepyEntity | Pet | Hub | DeviceConnectivity] = []

    spc: SurePetcareAPI = hass.data[DOMAIN][SPC]

    for surepy_entity in spc.states.values():

        entity = None

        if surepy_entity.type == EntityType.PET:
            entity = Pet(surepy_entity.id, spc)
            entities.append(entity)

        elif surepy_entity.type == EntityType.HUB:
            entity = Hub(surepy_entity.id, spc)
            entities.append(entity)

        # connectivity
        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(DeviceConnectivity(surepy_entity.id, spc))
        elif surepy_entity.type == EntityType.PET:
            entities.append(Pet(surepy_entity.id, spc))
        elif surepy_entity.type == EntityType.HUB:
            entities.append(Hub(surepy_entity.id, spc))

    async_add_entities(entities, True)


class SurePetcareBinarySensor(BinarySensorEntity):  # type: ignore
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(self, _id: int, spc: SurePetcareAPI, device_class: str):
        """Initialize a Sure Petcare binary sensor."""

        self._id = _id
        self._device_class = device_class

        self._spc: SurePetcareAPI = spc

        self._surepy_entity: SurepyEntity = self._spc.states[self._id]
        self._state: Any = None

        # cover special case where a device has no name set
        if surepy_entity.name:
            name = surepy_entity.name
        else:
            name = f"Unnamed {surepy_entity.type.name.capitalize()}"

        self._attr_device_class = device_class
        self._attr_name = f"{surepy_entity.type.name.capitalize()} {name.capitalize()}"
        self._attr_unique_id = f"{surepy_entity.household_id}-{self._id}"

    @abstractmethod
    @callback
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        self.async_schedule_update_ha_state(True)
        self._surepy_entity = self._spc.states[self._id]
        self._state = self._surepy_entity.raw_data()["status"]
        # _LOGGER.debug("🐾 %s updated", self._surepy_entity.name)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        self.async_on_remove(
            async_dispatcher_connect(self.hass, TOPIC_UPDATE, self._async_update)
        )

        @callback  # type: ignore
        def update() -> None:
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        async_dispatcher_connect(self.hass, TOPIC_UPDATE, update)

        self._async_update()


class Hub(SurePetcareBinarySensor):
    """Sure Petcare Hub."""

    def __init__(self, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Hub."""
        super().__init__(_id, spc, DEVICE_CLASS_CONNECTIVITY)  # , EntityType.HUB)

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return bool(self._state["online"])

    @property
    def is_on(self) -> bool:
        """Return true if entity is online."""
        return self.available

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._surepy_entity.raw_data():
            attributes = {
                "led_mode": int(self._surepy_entity.raw_data()["status"]["led_mode"]),
                "pairing_mode": bool(
                    self._surepy_entity.raw_data()["status"]["pairing_mode"]
                ),
            }
        else:
            self._attr_extra_state_attributes = {}
        _LOGGER.debug("%s -> state: %s", self.name, state)
        self.async_write_ha_state()


class Pet(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(self, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Pet."""
        super().__init__(_id, spc, DEVICE_CLASS_PRESENCE)  # , EntityType.PET)

        self._surepy_entity: SurePet
        self._state: PetLocation

    @property
    def is_on(self) -> bool:
        """Return true if entity is at home."""
        try:
            return bool(Location(self._state.where) == Location.INSIDE)
        except (KeyError, TypeError):
            return False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {
                "since": self._state.since,
                "where": self._state.where,
                **self._surepy_entity.raw_data(),
            }
        else:
            self._attr_extra_state_attributes = {}
        _LOGGER.debug("%s -> state: %s", self.name, state)
        self.async_write_ha_state()


class DeviceConnectivity(SurePetcareBinarySensor):
    """Sure Petcare Device."""

    def __init__(
        self,
        _id: int,
        # sure_type: EntityType,
        spc: SurePetcareAPI,
    ) -> None:
        """Initialize a Sure Petcare Device."""
        super().__init__(_id, spc, DEVICE_CLASS_CONNECTIVITY)
        self._attr_name = f"{self.name}_connectivity"
        self._attr_unique_id = (
            f"{self._spc.states[self._id].household_id}-{self._id}-connectivity"
        )

    @callback
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        surepy_entity = self._spc.states[self._id]
        state = surepy_entity.raw_data()["status"]
        self._attr_is_on = self._attr_available = bool(state)
        if state:
            self._attr_extra_state_attributes = {
                "device_rssi": f'{state["signal"]["device_rssi"]:.2f}',
                "hub_rssi": f'{state["signal"]["hub_rssi"]:.2f}',
            }
        else:
            self._attr_extra_state_attributes = {}
        _LOGGER.debug("%s -> state: %s", self.name, state)
        self.async_write_ha_state()
