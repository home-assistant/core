"""
Support for deCONZ binary sensor support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor/deconz/
"""

import asyncio
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.deconz import (
    ATTR_FW_VERSION, ATTR_MANUFACTURER, ATTR_MODEL_ID, ATTR_UNIQUE_ID,
    DECONZ_DATA, DOMAIN)
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import callback

DEPENDENCIES = [DOMAIN]

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup binary sensor platform for Deconz."""
    from pydeconz.sensor import DECONZ_BINARY_SENSOR
    sensors = hass.data[DECONZ_DATA].sensors

    for _, sensor in sensors.items():
        if sensor.type in DECONZ_BINARY_SENSOR:
            async_add_devices([DeconzBinarySensor(sensor)], True)


class DeconzBinarySensor(BinarySensorDevice):
    """Representation of a binary sensor."""

    def __init__(self, sensor):
        """Setup sensor and add update callback to get data from websocket."""
        self._sensor = sensor
        self._sensor.register_callback(self._update_callback)

    @callback
    def _update_callback(self):
        """Update the sensor's state, if needed."""
        self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._sensor.is_tripped

    @property
    def name(self):
        """Return the name of the event."""
        return self._sensor.name

    @property
    def device_class(self):
        """Class of the event."""
        return self._sensor.sensor_class

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._sensor.sensor_icon

    @property
    def available(self):
        """Return True if entity is available."""
        return self._sensor.reachable

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        from pydeconz.sensor import PRESENCE
        attr = {
            ATTR_BATTERY_LEVEL: self._sensor.battery,
            ATTR_FW_VERSION: self._sensor.swversion,
            ATTR_MANUFACTURER: self._sensor.manufacturer,
            ATTR_MODEL_ID: self._sensor.modelid,
            ATTR_UNIQUE_ID: self._sensor.uniqueid,
        }
        if self._sensor.type == PRESENCE:
            attr['dark'] = self._sensor.dark
        return attr
