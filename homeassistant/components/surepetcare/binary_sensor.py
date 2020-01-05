"""Support for Sure PetCare Flaps/Pets binary sensors."""
import logging

from surepy import SureLocationID, SureLockStateID, SureThingID

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_PRESENCE,
    BinarySensorDevice,
)
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_SURE_PETCARE, DEFAULT_DEVICE_CLASS, SPC, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Sure PetCare Flaps sensors based on a config entry."""
    if discovery_info is None:
        return

    entities = []

    spc = hass.data[DATA_SURE_PETCARE][SPC]

    for thing in spc.ids:
        sure_id = thing[CONF_ID]
        sure_type = thing[CONF_TYPE]

        if sure_type == SureThingID.FLAP.name:
            entity = Flap(sure_id, thing[CONF_NAME], spc)
        elif sure_type == SureThingID.PET.name:
            entity = Pet(sure_id, thing[CONF_NAME], spc)

        entities.append(entity)

    async_add_entities(entities, True)


class SurePetcareBinarySensor(BinarySensorDevice):
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(
        self, _id: int, name: str, spc, device_class: str, sure_type: SureThingID
    ):
        """Initialize a Sure Petcare binary sensor."""
        self._id = _id
        self._name = name
        self._spc = spc
        self._device_class = device_class
        self._sure_type = sure_type
        self._state = {}

        self._async_unsub_dispatcher_connect = None

    @property
    def is_on(self):
        """Return true if entity is on/unlocked."""
        return bool(self._state)

    @property
    def should_poll(self):
        """Return true."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state

    @property
    def device_class(self):
        """Return the device class."""
        return DEFAULT_DEVICE_CLASS if not self._device_class else self._device_class

    @property
    def unique_id(self):
        """Return an unique ID."""
        return f"{self._spc.household_id}-{self._id}"

    async def async_update(self):
        """Get the latest data and update the state."""
        self._state = self._spc.states[self._sure_type][self._id].get("data")

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()


class Flap(SurePetcareBinarySensor):
    """Sure Petcare Flap."""

    def __init__(self, _id: int, name: str, spc):
        """Initialize a Sure Petcare Flap."""
        super().__init__(
            _id,
            f"Flap {name.capitalize()}",
            spc,
            DEVICE_CLASS_LOCK,
            SureThingID.FLAP.name,
        )

    @property
    def is_on(self):
        """Return true if entity is on/unlocked."""
        try:
            return bool(self._state["locking"]["mode"] == SureLockStateID.UNLOCKED)
        except (KeyError, TypeError):
            return None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            try:
                attributes = {
                    "battery_voltage": self._state["battery"] / 4,
                    "locking_mode": self._state["locking"]["mode"],
                    "device_rssi": self._state["signal"]["device_rssi"],
                    "hub_rssi": self._state["signal"]["hub_rssi"],
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

    def __init__(self, _id: int, name: str, spc):
        """Initialize a Sure Petcare Pet."""
        super().__init__(
            _id,
            f"Pet {name.capitalize()}",
            spc,
            DEVICE_CLASS_PRESENCE,
            SureThingID.PET.name,
        )

    @property
    def is_on(self):
        """Return true if entity is at home."""
        try:
            return bool(self._state["where"] == SureLocationID.INSIDE)
        except (KeyError, TypeError):
            return False
