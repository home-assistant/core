"""Support for Sure PetCare Flaps binary sensors."""
import logging

from homeassistant.components.binary_sensor import DEVICE_CLASS_LOCK, BinarySensorDevice
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CONF_DATA,
    CONF_HOUSEHOLD_ID,
    DATA_SURE_PETCARE,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_ICON,
    SURE_IDS,
    TOPIC_UPDATE,
    SureLocationID,
    SureLockStateID,
    SureThingID,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Sure PetCare Flaps sensors based on a config entry."""
    if not discovery_info:
        return

    entities = []

    for thing in hass.data[DATA_SURE_PETCARE][SURE_IDS]:
        sure_id = thing[CONF_ID]
        sure_type = thing[CONF_TYPE]
        sure_data = thing[CONF_DATA]

        if sure_id not in hass.data[DATA_SURE_PETCARE][sure_type]:
            if sure_type == SureThingID.FLAP.name:
                hass.data[DATA_SURE_PETCARE][sure_type][sure_id] = sure_data
                entities.append(Flap(sure_id, thing[CONF_NAME]))
            elif sure_type == SureThingID.PET.name:
                hass.data[DATA_SURE_PETCARE][sure_type][sure_id] = sure_data
                entities.append(Pet(sure_id, thing[CONF_NAME]))

    async_add_entities(entities, True)


class SurePetcareBinarySensor(BinarySensorDevice):
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(
        self, _id: int, name: str, icon=None, device_class=None, sure_type=None
    ):
        """Initialize a Sure Petcare binary sensor."""
        self._id = _id
        self._name = name
        self._unit_of_measurement = "%"
        self._icon = icon
        self._device_class = device_class
        self._sure_type = sure_type
        self._state = {}

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
    def icon(self):
        """Return the device class."""
        return DEFAULT_ICON if not self._icon else self._icon

    @property
    def unique_id(self):
        """Return an unique ID."""
        return f"{self._household_id}-{self._id}"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the latest data and update the state."""
        try:
            self._state = self._hass.data[DATA_SURE_PETCARE][self._sure_type][self._id]
        except (AttributeError, KeyError, TypeError) as error:
            _LOGGER.debug("Async_update error: %s", error)

    async def async_added_to_hass(self):
        """Register callbacks."""

        # pylint: disable=attribute-defined-outside-init
        self._household_id = self.hass.data[DATA_SURE_PETCARE][CONF_HOUSEHOLD_ID]
        self._data = self.hass.data[DATA_SURE_PETCARE][self._sure_type]

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        # pylint: disable=attribute-defined-outside-init
        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()


class Flap(SurePetcareBinarySensor):
    """Sure Petcare Flap."""

    def __init__(self, _id: int, name: str, hass=None):
        """Initialize a Sure Petcare Flap."""
        super().__init__(
            _id,
            f"Flap {name.capitalize()}",
            device_class=DEVICE_CLASS_LOCK,
            sure_type=SureThingID.FLAP.name,
            hass=hass,
        )

    @property
    def is_on(self):
        """Return true if light is on."""
        try:
            return bool(self._state["locking"]["mode"] == SureLockStateID.UNLOCKED)
        except (KeyError, TypeError):
            return None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        try:
            attributes = {
                "battery_voltage": self._state["battery"] / 4,
                "locking_mode": self._state["locking"]["mode"],
                "device_rssi": self._state["signal"]["device_rssi"],
                "hub_rssi": self._state["signal"]["hub_rssi"],
                "mac_address": self._state["mac_address"],
                "version": self._state["version"],
            }

        except (KeyError, TypeError) as error:
            _LOGGER.debug(
                "Error getting device state attributes from %s: %s\n\n%s",
                self._name,
                error,
                self._state,
            )
            attributes = {"error": self._state}

        return attributes


class Pet(SurePetcareBinarySensor):
    """Sure Petcare Pet."""

    def __init__(self, _id: int, name: str, hass=None):
        """Initialize a Sure Petcare Pet."""
        super().__init__(
            _id,
            f"Pet {name.capitalize()}",
            icon="mdi:cat",
            device_class="presence",
            sure_type=SureThingID.PET.name,
            hass=hass,
        )

    @property
    def is_on(self):
        """Return true if light is on."""
        try:
            return bool(self._state["where"] == SureLocationID.INSIDE)
        except (KeyError, TypeError):
            return False
