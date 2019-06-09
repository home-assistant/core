"""Support for Sure PetCare Flaps binary sensors."""
import logging

import homeassistant.helpers.device_registry as dr
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (CONF_HOUSEHOLD_ID, DATA_SURE_PETCARE, DATA_SUREPY,
                    DEFAULT_DEVICE_CLASS, DEFAULT_ICON, SURE_IDS, TOPIC_UPDATE,
                    SureLocationID, SureLockStateID, SureProductID,
                    SureThingID)

_LOGGER = logging.getLogger(__name__)


# async def async_setup_entry(hass, entry, async_add_entities):
async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up Sure PetCare Flaps sensors based on a config entry."""
    from surepy import SurePetcare

    entities = list()
    surepy: SurePetcare = hass.data[DATA_SURE_PETCARE][DATA_SUREPY]

    for thing in hass.data[DATA_SURE_PETCARE][SURE_IDS]:
        sure_id = thing[CONF_ID]
        sure_type = thing[CONF_TYPE]

        if sure_id not in hass.data[DATA_SURE_PETCARE][sure_type]:

            if sure_type == SureThingID.FLAP.name:
                hass.data[DATA_SURE_PETCARE][
                    sure_type][sure_id] = await surepy.get_flap_data(sure_id)
                entities.append(Flap(sure_id, thing[CONF_NAME], hass=hass))
            elif sure_type == SureThingID.PET.name:
                hass.data[DATA_SURE_PETCARE][
                    sure_type][sure_id] = await surepy.get_pet_data(sure_id)
                entities.append(Pet(sure_id, thing[CONF_NAME], hass=hass))

    async_add_entities(entities, True)


class SurePetcareBinarySensor(BinarySensorDevice):
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(self, _id: int, name: str,
                 icon=None, device_class=None, sure_type=None, hass=None):
        """Initialize a Sure Petcare binary sensor."""
        self._id = _id
        self._hass = hass
        self._name = name
        self._unit_of_measurement = "%"
        self._icon = icon
        self._device_class = device_class

        self._household_id = hass.data[DATA_SURE_PETCARE][CONF_HOUSEHOLD_ID]
        self._sure_type = sure_type

        self._state = dict()
        self._data = hass.data[DATA_SURE_PETCARE][sure_type]

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
        return (DEFAULT_DEVICE_CLASS
                if not self._device_class
                else self._device_class)

    @property
    def icon(self):
        """Return the device class."""
        return DEFAULT_ICON if not self._icon else self._icon

    @property
    def unique_id(self):
        """Return an unique ID."""
        return "{}-{}".format(self._household_id, self._id)

    async def async_update(self):
        """Get the latest data and update the state."""
        try:
            self._state = self._hass.data[
                DATA_SURE_PETCARE][self._sure_type][self._id]
        except (AttributeError, KeyError, TypeError) as error:
            _LOGGER.debug("async_update error: %s", error)

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        # pylint: disable=attribute-defined-outside-init
        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self._hass, TOPIC_UPDATE, update)

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
            icon="mdi:lock",
            device_class="lock",
            sure_type=SureThingID.FLAP.name,
            hass=hass,
        )

    @property
    def is_on(self):
        """Return true if light is on."""
        try:
            return bool(
                self._state["locking"]["mode"] == SureLockStateID.UNLOCKED)
        except (KeyError, TypeError):
            return "unknown"

    @property
    def device_info(self):
        """Return information about the device."""
        try:
            device_info = {
                "name": self._name,
                "model": SureProductID.PET_FLAP,
                "manufacturer": 'Sure Petcare',
                "connections": {
                    (dr.CONNECTION_NETWORK_MAC,
                     self._state["mac_address"] or "DEAD1337BEEF1337")
                },
                "sw_version": self._state["version"] or 0,
            }
        except TypeError as error:
            device_info = None
            _LOGGER.debug(
                "error getting device info from %s: %s\n\n%s",
                self._name, error, self._state)

        return device_info

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        try:
            attributes = dict(
                battery_voltage=self._state["battery"] / 4,
                locking_mode=self._state["locking"]["mode"],
                device_rssi=self._state["signal"]["device_rssi"],
                hub_rssi=self._state["signal"]["hub_rssi"],
                mac_address=self._state["mac_address"],
                version=self._state["version"],
            )

        except (KeyError, TypeError) as error:
            _LOGGER.debug(
                "error getting device state attributes from %s: %s\n\n%s",
                self._name, error, self._state)
            attributes = dict(error=self._state)

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
