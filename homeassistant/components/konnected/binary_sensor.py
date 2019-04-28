"""Support for wired binary sensors attached to a Konnected device."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_STATE, CONF_BINARY_SENSORS, CONF_DEVICES, CONF_NAME,
    CONF_TYPE)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN as KONNECTED_DOMAIN, PIN_TO_ZONE, SIGNAL_SENSOR_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up binary sensors attached to a Konnected device."""
    if discovery_info is None:
        return

    data = hass.data[KONNECTED_DOMAIN]
    device_id = discovery_info['device_id']
    sensors = [KonnectedBinarySensor(device_id, pin_num, pin_data)
               for pin_num, pin_data in
               data[CONF_DEVICES][device_id][CONF_BINARY_SENSORS].items()]
    async_add_entities(sensors)


class KonnectedBinarySensor(BinarySensorDevice):
    """Representation of a Konnected binary sensor."""

    def __init__(self, device_id, pin_num, data):
        """Initialize the Konnected binary sensor."""
        self._data = data
        self._device_id = device_id
        self._pin_num = pin_num
        self._state = self._data.get(ATTR_STATE)
        self._device_class = self._data.get(CONF_TYPE)
        self._unique_id = '{}-{}'.format(device_id, PIN_TO_ZONE[pin_num])
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

    async def async_added_to_hass(self):
        """Store entity_id and register state change callback."""
        self._data[ATTR_ENTITY_ID] = self.entity_id
        async_dispatcher_connect(
            self.hass, SIGNAL_SENSOR_UPDATE.format(self.entity_id),
            self.async_set_state)

    @callback
    def async_set_state(self, state):
        """Update the sensor's state."""
        self._state = state
        self.async_schedule_update_ha_state()
