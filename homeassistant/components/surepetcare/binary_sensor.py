"""Support for Sure PetCare Flaps/Pets binary sensors."""
from __future__ import annotations

from abc import abstractmethod
import logging

from surepy.entities import SurepyEntity
from surepy.enums import EntityType, Location

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PRESENCE,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import SurePetcareAPI
from .const import DOMAIN, SPC, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
) -> None:
    """Set up Sure PetCare Flaps sensors based on a config entry."""
    if discovery_info is None:
        return

    entities: list[SurepyEntity] = []

    spc: SurePetcareAPI = hass.data[DOMAIN][SPC]

    for surepy_entity in spc.states.values():

        # connectivity
        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(DeviceConnectivity(surepy_entity.id, spc))

        if surepy_entity.type == EntityType.PET:
            entities.append(Pet(surepy_entity.id, spc))
        elif surepy_entity.type == EntityType.HUB:
            entities.append(Hub(surepy_entity.id, spc))

    async_add_entities(entities, True)


class SurePetcareBinarySensor(BinarySensorEntity):
    """A binary sensor implementation for Sure Petcare Entities."""

    _attr_should_poll = False

    def __init__(
        self,
        _id: int,
        spc: SurePetcareAPI,
        device_class: str,
    ) -> None:
        """Initialize a Sure Petcare binary sensor."""

        self._id = _id
        self._spc: SurePetcareAPI = spc

        surepy_entity: SurepyEntity = self._spc.states[self._id]

        # cover special case where a device has no name set
        if surepy_entity.name:
            name = surepy_entity.name
        else:
            name = f"Unnamed {surepy_entity.type.name.capitalize()}"

        self._name = f"{surepy_entity.type.name.capitalize()} {name.capitalize()}"

        self._attr_device_class = device_class
        self._attr_unique_id = f"{surepy_entity.household_id}-{self._id}"

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self._name

    @abstractmethod
    @callback
    def _async_update(self) -> None:
        """Get the latest data and update the state."""

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, TOPIC_UPDATE, self._async_update)
        )
        self._async_update()


class Hub(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(self, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Hub."""
        super().__init__(_id, spc, DEVICE_CLASS_CONNECTIVITY)

    @callback
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        surepy_entity = self._spc.states[self._id]
        state = surepy_entity.raw_data()["status"]
        self._attr_is_on = self._attr_available = bool(state["online"])
        if surepy_entity.raw_data():
            self._attr_extra_state_attributes = {
                "led_mode": int(surepy_entity.raw_data()["status"]["led_mode"]),
                "pairing_mode": bool(
                    surepy_entity.raw_data()["status"]["pairing_mode"]
                ),
            }
        else:
            self._attr_extra_state_attributes = None
        _LOGGER.debug("%s -> state: %s", self._name, state)
        self.async_write_ha_state()


class Pet(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(self, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Pet."""
        super().__init__(_id, spc, DEVICE_CLASS_PRESENCE)

    @callback
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        surepy_entity = self._spc.states[self._id]
        state = surepy_entity.location
        try:
            self._attr_is_on = bool(Location(state.where) == Location.INSIDE)
        except (KeyError, TypeError):
            self._attr_is_on = False
        if state:
            self._attr_extra_state_attributes = {
                "since": state.since,
                "where": state.where,
            }
        else:
            self._attr_extra_state_attributes = None
        _LOGGER.debug("%s -> state: %s", self._name, state)
        self.async_write_ha_state()


class DeviceConnectivity(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(
        self,
        _id: int,
        spc: SurePetcareAPI,
    ) -> None:
        """Initialize a Sure Petcare Device."""
        super().__init__(_id, spc, DEVICE_CLASS_CONNECTIVITY)
        self._attr_unique_id = (
            f"{self._spc.states[self._id].household_id}-{self._id}-connectivity"
        )

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self._name}_connectivity"

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
            self._attr_extra_state_attributes = None
        _LOGGER.debug("%s -> state: %s", self._name, state)
        self.async_write_ha_state()
