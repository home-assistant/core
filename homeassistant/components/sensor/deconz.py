"""Platform integrating Deconz sensor support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/deconz/
"""

import asyncio
import logging

from homeassistant.components.deconz import (
    DECONZ_DATA, DOMAIN, TYPE_AS_EVENT)
from homeassistant.core import (callback, EventOrigin)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send, async_dispatcher_connect)
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

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
            if sensor.type in type_as_event:
                DeconzEvent(hass, sensor)
                if sensor.battery:
                    async_add_devices([DeconzBattery(hass, sensor)], True)
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
        self._signal = DOMAIN + '_' + self._device.name

    @callback
    def _update_callback(self):
        """Fire the event."""
        event = 'deconz_event'
        data = {'id': self._device.name, 'event': self._device.state}
        self._hass.bus.async_fire(event, data, EventOrigin.remote)
        async_dispatcher_send(self._hass, self._signal)


class DeconzBattery(Entity):
    """Battery class for when a device is only represented as an event."""

    def __init__(self, hass, device):
        """Register dispatcher callback for update of battery state."""
        self._device = device
        self._battery = device.battery
        self._name = self._device.name + '_battery'
        signal = DOMAIN + '_' + self._device.name
        async_dispatcher_connect(hass, signal, self._update_callback)

    @callback
    def _update_callback(self):
        """Update the battery's state, if needed."""
        if self._battery != self._device.battery:
            self._battery = self._device.battery
            self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the battery."""
        return self._battery

    @property
    def name(self):
        """Return the name of the battery."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False
