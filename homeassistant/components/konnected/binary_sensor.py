"""Support for wired binary sensors attached to a Konnected device."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_STATE,
    CONF_BINARY_SENSORS,
    CONF_DEVICES,
    CONF_NAME,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN as KONNECTED_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up binary sensors attached to a Konnected device from a config entry."""
    data = hass.data[KONNECTED_DOMAIN]
    device_id = config_entry.data["id"]
    sensors = [
        KonnectedBinarySensor(device_id, pin_num, pin_data)
        for pin_num, pin_data in data[CONF_DEVICES][device_id][
            CONF_BINARY_SENSORS
        ].items()
    ]
    async_add_entities(sensors)


class KonnectedBinarySensor(BinarySensorDevice):
    """Representation of a Konnected binary sensor."""

    def __init__(self, device_id, zone_num, data):
        """Initialize the Konnected binary sensor."""
        self._data = data
        self._device_id = device_id
        self._zone_num = zone_num
        self._state = self._data.get(ATTR_STATE)
        self._device_class = self._data.get(CONF_TYPE)
        self._unique_id = f"{device_id}-{zone_num}"
        self._name = self._data.get(CONF_NAME)

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(KONNECTED_DOMAIN, self._device_id)},
        }

    async def async_added_to_hass(self):
        """Store entity_id and register state change callback."""
        self._data[ATTR_ENTITY_ID] = self.entity_id
        async_dispatcher_connect(
            self.hass, f"konnected.{self.entity_id}.update", self.async_set_state
        )

    @callback
    def async_set_state(self, state):
        """Update the sensor's state."""
        self._state = state
        self.async_write_ha_state()
