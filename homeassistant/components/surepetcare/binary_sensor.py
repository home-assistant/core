"""Support for Sure PetCare Flaps/Pets binary sensors."""
from datetime import datetime
import logging
from typing import Any, Dict, Optional

from surepy import SureLocationID, SureProductID

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PRESENCE,
    BinarySensorEntity,
)
from homeassistant.const import CONF_ID, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import SurePetcareAPI
from .const import DATA_SURE_PETCARE, SPC, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
) -> None:
    """Set up Sure PetCare Flaps sensors based on a config entry."""
    if discovery_info is None:
        return

    entities = []

    spc = hass.data[DATA_SURE_PETCARE][SPC]

    for thing in spc.ids:
        sure_id = thing[CONF_ID]
        sure_type = thing[CONF_TYPE]

        # connectivity
        if sure_type in [
            SureProductID.CAT_FLAP,
            SureProductID.PET_FLAP,
            SureProductID.FEEDER,
        ]:
            entities.append(DeviceConnectivity(sure_id, sure_type, spc))

        if sure_type == SureProductID.PET:
            entity = Pet(sure_id, spc)
        elif sure_type == SureProductID.HUB:
            entity = Hub(sure_id, spc)
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
        sure_type: SureProductID,
    ):
        """Initialize a Sure Petcare binary sensor."""
        self._id = _id
        self._sure_type = sure_type
        self._device_class = device_class

        self._spc: SurePetcareAPI = spc
        self._spc_data: Dict[str, Any] = self._spc.states[self._sure_type].get(self._id)
        self._state: Dict[str, Any] = {}

        # cover special case where a device has no name set
        if "name" in self._spc_data:
            name = self._spc_data["name"]
        else:
            name = f"Unnamed {self._sure_type.name.capitalize()}"

        self._name = f"{self._sure_type.name.capitalize()} {name.capitalize()}"

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
    def device_class(self) -> str:
        """Return the device class."""
        return None if not self._device_class else self._device_class

    @property
    def unique_id(self: BinarySensorEntity) -> str:
        """Return an unique ID."""
        return f"{self._spc_data['household_id']}-{self._id}"

    async def async_update(self) -> None:
        """Get the latest data and update the state."""
        self._spc_data = self._spc.states[self._sure_type].get(self._id)
        self._state = self._spc_data.get("status")
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
        super().__init__(_id, spc, DEVICE_CLASS_CONNECTIVITY, SureProductID.HUB)

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return bool(self._state["online"])

    @property
    def is_on(self) -> bool:
        """Return true if entity is online."""
        return self.available

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {
                "led_mode": int(self._state["led_mode"]),
                "pairing_mode": bool(self._state["pairing_mode"]),
            }

        return attributes


class Pet(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(self, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare Pet."""
        super().__init__(_id, spc, DEVICE_CLASS_PRESENCE, SureProductID.PET)

    @property
    def is_on(self) -> bool:
        """Return true if entity is at home."""
        try:
            return bool(SureLocationID(self._state["where"]) == SureLocationID.INSIDE)
        except (KeyError, TypeError):
            return False

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {
                "since": str(
                    datetime.fromisoformat(self._state["since"]).replace(tzinfo=None)
                ),
                "where": SureLocationID(self._state["where"]).name.capitalize(),
            }

        return attributes

    async def async_update(self) -> None:
        """Get the latest data and update the state."""
        self._spc_data = self._spc.states[self._sure_type].get(self._id)
        self._state = self._spc_data.get("position")
        _LOGGER.debug("%s -> self._state: %s", self._name, self._state)


class DeviceConnectivity(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(
        self, _id: int, sure_type: SureProductID, spc: SurePetcareAPI,
    ) -> None:
        """Initialize a Sure Petcare Device."""
        super().__init__(_id, spc, DEVICE_CLASS_CONNECTIVITY, sure_type)

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self._name}_connectivity"

    @property
    def unique_id(self: BinarySensorEntity) -> str:
        """Return an unique ID."""
        return f"{self._spc_data['household_id']}-{self._id}-connectivity"

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return bool(self._state)

    @property
    def is_on(self) -> bool:
        """Return true if entity is online."""
        return self.available

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {
                "device_rssi": f'{self._state["signal"]["device_rssi"]:.2f}',
                "hub_rssi": f'{self._state["signal"]["hub_rssi"]:.2f}',
            }

        return attributes
