"""
Support for deCONZ sensor support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/deconz/
"""

import asyncio
import logging

from homeassistant.components.deconz import (
    CONF_SWITCH_AS_EVENT, DECONZ_DATA, DOMAIN, DeconzEvent)
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util import slugify

DEPENDENCIES = [DOMAIN]

_LOGGER = logging.getLogger(__name__)

ATTR_EVENT_ID = 'event_id'


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup sensor platform for Deconz."""
    if discovery_info is None:
        return False

    from pydeconz.sensor import DECONZ_SENSOR
    switch_as_event = discovery_info.get(CONF_SWITCH_AS_EVENT)
    sensors = hass.data[DECONZ_DATA].sensors
    entities = []

    for sensor in sensors.values():
        if sensor.type in DECONZ_SENSOR:
            if switch_as_event and sensor.type == 'ZHASwitch':
                DeconzEvent(hass, sensor)
                if sensor.battery:
                    entities.append(DeconzBattery(sensor))
            else:
                entities.append(DeconzSensor(sensor))
    async_add_devices(entities, True)


class DeconzSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, sensor):
        """Setup sensor and add update callback to get data from websocket."""
        self._sensor = sensor
        self._sensor.register_callback(self._update_callback)

    @callback
    def _update_callback(self, reason):
        """Update the sensor's state, if reason is that state is updated."""
        if reason['state']:
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
    def device_class(self):
        """Class of the event."""
        return self._sensor.sensor_class

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._sensor.sensor_icon

    @property
    def unit_of_measurement(self):
        """Unit of measurement of this entity."""
        return self._sensor.sensor_unit

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
        attr = {
            ATTR_BATTERY_LEVEL: self._sensor.battery,
        }
        return attr


class DeconzBattery(Entity):
    """Battery class for when a device is only represented as an event."""

    def __init__(self, device):
        """Register dispatcher callback for update of battery state."""
        self._device = device
        self._battery = device.battery
        self._name = self._device.name + ' battery level'
        self._device_class = 'battery'
        self._unit_of_measurement = "%"
        self._device.register_callback(self._update_callback)

    @callback
    def _update_callback(self, reason):
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
    def device_class(self):
        """Class of the event."""
        return self._device_class

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return icon_for_battery_level(int(self.state))

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr = {
            ATTR_EVENT_ID: slugify(self._device.name),
        }
        return attr
