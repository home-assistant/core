"""Support for Sure PetCare Flaps/Pets binary sensors."""
from __future__ import annotations

import logging
from typing import Any

from surepy.entities import SurepyEntity
from surepy.enums import EntityType, Location, SureEnum

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

    # for thing in spc.ids:
    for entity in (await spc.surepy.get_entities()).values():

        # connectivity
        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(DeviceConnectivity(surepy_entity.id, surepy_entity.type, spc))

        if surepy_entity.type == EntityType.PET:
            entity = Pet(surepy_entity.id, spc)
        elif surepy_entity.type == EntityType.HUB:
            entity = Hub(surepy_entity.id, spc)
        else:
            continue

        entities.append(entity)

    async_add_entities(entities, True)


class SurePetcareBinarySensor(BinarySensorEntity):
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(
        self,
        _id: int,
        spc: SurePetcareAPI,
        device_class: str,
        sure_type: EntityType,
    ):
        """Initialize a Sure Petcare binary sensor."""

        self._id = _id
        self._device_class = device_class

        self._spapi: SurePetcareAPI = spc

        self._surepy_entity: SurepyEntity = self._spc.states[self._id]
        self._state: SureEnum | dict[str, Any] = None

        # cover special case where a device has no name set
        if self._entity.name:
            name = self._entity.name
        else:
            name = f"Unnamed {self._surepy_entity.type.name.capitalize()}"

        self._name = f"{self._surepy_entity.type.name.capitalize()} {name.capitalize()}"

        self._async_unsub_dispatcher_connect = None

    @property
    def is_on(self) -> bool | None:
        """Return true if entity is on/unlocked."""
        return bool(self._state)

    @property
    def should_poll(self) -> bool:
        """Return true."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self._name

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return None if not self._device_class else self._device_class

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._surepy_entity.household_id}-{self._id}"

    async def async_update(self) -> None:
        """Get the latest data and update the state."""
        self._surepy_entity = self._spc_.states[self._id]
        self._state = self._entity._data["status"]
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


class Hub(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(self, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Hub."""
        super().__init__(_id, spc, DEVICE_CLASS_CONNECTIVITY, EntityType.HUB)

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
        if self._entity._data:
            attributes = {
                "led_mode": int(self._entity._data["status"]["led_mode"]),
                "pairing_mode": bool(self._entity._data["status"]["pairing_mode"]),
            }

        return attributes


class Pet(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(self, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Pet."""
        super().__init__(_id, spc, DEVICE_CLASS_PRESENCE, EntityType.PET)

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
            attributes = {"since": self._state.since, "where": self._state.where}

        return attributes

    async def async_update(self) -> None:
        """Get the latest data and update the state."""
        self._entity = self._spapi._states[self._id]
        self._state = self._entity.location
        _LOGGER.debug("%s -> self._state: %s", self._name, self._state)


class DeviceConnectivity(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(
        self,
        _id: int,
        sure_type: EntityType,
        spc: SurePetcareAPI,
    ) -> None:
        """Initialize a Sure Petcare Device."""
        super().__init__(_id, spc, DEVICE_CLASS_CONNECTIVITY, sure_type)

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self._name}_connectivity"

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._entity.household_id}-{self._id}-connectivity"

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return bool(self._state)

    @property
    def is_on(self) -> bool:
        """Return true if entity is online."""
        return self.available

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {
                "device_rssi": f'{self._state["signal"]["device_rssi"]:.2f}',
                "hub_rssi": f'{self._state["signal"]["hub_rssi"]:.2f}',
            }

        return attributes
