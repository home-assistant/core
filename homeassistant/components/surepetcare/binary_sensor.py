"""Support for Sure PetCare Flaps/Pets binary sensors."""
from datetime import datetime
import logging
from typing import Any, Dict, Optional

from surepy import SureLocationID, SureLockStateID, SureThingID

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_PRESENCE,
    BinarySensorDevice,
)
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import SurePetcareAPI
from .const import DATA_SURE_PETCARE, DEFAULT_DEVICE_CLASS, SPC, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
) -> None:
    """Set up Sure PetCare Flaps sensors based on a config entry."""
    if discovery_info is None:
        return

    entities = []

    spc = hass.data[DATA_SURE_PETCARE][SPC]

    _LOGGER.debug("async_setup_platform() - spc.ids: %s", spc.ids)

    for thing in spc.ids:
        sure_id = thing[CONF_ID]
        sure_type = thing[CONF_TYPE]

        if sure_type == SureThingID.FLAP:
            entity = Flap(sure_id, thing[CONF_NAME], spc)
        elif sure_type == SureThingID.PET:
            entity = Pet(sure_id, thing[CONF_NAME], spc)

        entities.append(entity)

    async_add_entities(entities, True)


class SurePetcareBinarySensor(BinarySensorDevice):
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(
        self: BinarySensorDevice,
        _id: int,
        name: str,
        spc: SurePetcareAPI,
        device_class: str,
        sure_type: SureThingID,
    ):
        """Initialize a Sure Petcare binary sensor."""
        self._id = _id
        self._name = name
        self._spc = spc
        self._device_class = device_class
        self._sure_type = sure_type
        self._state: Dict[str, Any] = {}

        self._async_unsub_dispatcher_connect = None

    @property
    def is_on(self) -> Optional[bool]:
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
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the device."""
        if "since" in self._state:
            self._state["since"] = str(
                datetime.fromisoformat(self._state["since"]).replace(tzinfo=None)
            )
        if "where" in self._state:
            self._state["where"] = SureLocationID(
                self._state["where"]
            ).name.capitalize()
        _LOGGER.debug("device_state_attributes() - self._state: %s", self._state)
        return self._state

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return DEFAULT_DEVICE_CLASS if not self._device_class else self._device_class

    @property
    def unique_id(self: BinarySensorDevice) -> str:
        """Return an unique ID."""
        return f"{self._spc.household_id}-{self._id}"

    async def async_update(self) -> None:
        """Get the latest data and update the state."""
        self._state = self._spc.states[self._sure_type][self._id].get("data")
        _LOGGER.debug("async_update(): - self._state: %s", self._state)

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


class Flap(SurePetcareBinarySensor):
    """Sure Petcare Flap."""

    def __init__(
        self: BinarySensorDevice, _id: int, name: str, spc: SurePetcareAPI
    ) -> None:
        """Initialize a Sure Petcare Flap."""
        super().__init__(
            _id, f"Flap {name.capitalize()}", spc, DEVICE_CLASS_LOCK, SureThingID.FLAP,
        )

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if entity is on/unlocked."""
        try:
            return bool(self._state["locking"]["mode"] == SureLockStateID.UNLOCKED)
        except (KeyError, TypeError):
            return None

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            try:
                attributes = {
                    "online": bool(self._state["online"]),
                    "learn_mode": bool(self._state["learn_mode"]),
                    "battery_voltage": f'{self._state["battery"] / 4:.2f}',
                    "locking_mode": SureLockStateID(
                        self._state["locking"]["mode"]
                    ).name.capitalize(),
                    "device_rssi": f'{self._state["signal"]["device_rssi"]:.2f}',
                    "hub_rssi": f'{self._state["signal"]["hub_rssi"]:.2f}',
                }

            except (KeyError, TypeError) as error:
                _LOGGER.error(
                    "Error getting device state attributes from %s: %s\n\n%s",
                    self._name,
                    error,
                    self._state,
                )
                attributes = self._state

        return attributes


class Pet(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(
        self: BinarySensorDevice, _id: int, name: str, spc: SurePetcareAPI
    ) -> None:
        """Initialize a Sure Petcare Pet."""
        super().__init__(
            _id,
            f"Pet {name.capitalize()}",
            spc,
            DEVICE_CLASS_PRESENCE,
            SureThingID.PET,
        )

    @property
    def is_on(self) -> bool:
        """Return true if entity is at home."""
        try:
            return bool(SureLocationID(self._state["where"]) == SureLocationID.INSIDE)
        except (KeyError, TypeError):
            return False
