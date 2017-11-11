"""Platform integrating Deconz sensor support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/deconz/
"""

import asyncio
import logging

from homeassistant.components.deconz import (
    DECONZ_DATA, DOMAIN, TYPE_AS_EVENT)
from homeassistant.core import (callback, EventOrigin)
from homeassistant.helpers.entity import Entity

DEPENDENCIES = [DOMAIN]

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup sensor platform for Deconz."""
    from pydeconz.sensor import DECONZ_SENSOR

    type_as_event = discovery_info.get(TYPE_AS_EVENT)

    if DECONZ_DATA in hass.data:
        sensors = hass.data[DECONZ_DATA].sensors

    for _, sensor in sensors.items():
        if sensor.type in DECONZ_SENSOR:
            if sensor.type == type_as_event:
                DeconzEvent(hass, sensor)
            else:
                async_add_devices([DeconzSensor(sensor)], True)


class DeconzSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, sensor):
        """Setup sensor and add update callback to get data from websocket."""
        self._sensor = sensor
        self._sensor.register_callback(self._update_callback)

    @callback
    def _update_callback(self):
        """Update the sensor's state, if needed."""
        self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._sensor.state

    @property
    def name(self):
        """Return the name of the event."""
        return self._sensor.name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr = {
            'battery': self._sensor.battery,
            'manufacturer': self._sensor.manufacturer,
            'modelid': self._sensor.modelid,
            'reachable': self._sensor.reachable,
            'swversion': self._sensor.swversion,
            'uniqueid': self._sensor.uniqueid,
        }
        return attr


class DeconzEvent(object):
    """When you want signals instead of entities."""

    def __init__(self, hass, device):
        """Register callback that will be used for signals."""
        self._hass = hass
        self._device = device
        self._device.register_callback(self._update_callback)

    @callback
    def _update_callback(self):
        """Fire the event."""
        event = 'deconz_event'
        data = {'id': self._device.name, 'event': self._device.state}
        self._hass.bus.async_fire(event, data, EventOrigin.remote)
