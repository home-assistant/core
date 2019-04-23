"""Support for deCONZ binary sensors."""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_DARK, ATTR_ON, CONF_ALLOW_CLIP_SENSOR, DOMAIN as DECONZ_DOMAIN,
    NEW_SENSOR)
from .deconz_device import DeconzDevice

DEPENDENCIES = ['deconz']

ATTR_ORIENTATION = 'orientation'
ATTR_TILTANGLE = 'tiltangle'
ATTR_VIBRATIONSTRENGTH = 'vibrationstrength'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up deCONZ binary sensors."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the deCONZ binary sensor."""
    gateway = hass.data[DECONZ_DOMAIN]

    @callback
    def async_add_sensor(sensors):
        """Add binary sensor from deCONZ."""
        from pydeconz.sensor import DECONZ_BINARY_SENSOR
        entities = []
        allow_clip_sensor = config_entry.data.get(CONF_ALLOW_CLIP_SENSOR, True)
        for sensor in sensors:
            if sensor.type in DECONZ_BINARY_SENSOR and \
               not (not allow_clip_sensor and sensor.type.startswith('CLIP')):
                entities.append(DeconzBinarySensor(sensor, gateway))
        async_add_entities(entities, True)

    gateway.listeners.append(
        async_dispatcher_connect(hass, NEW_SENSOR, async_add_sensor))

    async_add_sensor(gateway.api.sensors.values())


class DeconzBinarySensor(DeconzDevice, BinarySensorDevice):
    """Representation of a deCONZ binary sensor."""

    @callback
    def async_update_callback(self, reason):
        """Update the sensor's state.

        If reason is that state is updated,
        or reachable has changed or battery has changed.
        """
        if reason['state'] or \
           'reachable' in reason['attr'] or \
           'battery' in reason['attr'] or \
           'on' in reason['attr']:
            self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._device.is_tripped

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device.sensor_class

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._device.sensor_icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        from pydeconz.sensor import PRESENCE, VIBRATION
        attr = {}
        if self._device.battery:
            attr[ATTR_BATTERY_LEVEL] = self._device.battery
        if self._device.on is not None:
            attr[ATTR_ON] = self._device.on
        if self._device.type in PRESENCE and self._device.dark is not None:
            attr[ATTR_DARK] = self._device.dark
        elif self._device.type in VIBRATION:
            attr[ATTR_ORIENTATION] = self._device.orientation
            attr[ATTR_TILTANGLE] = self._device.tiltangle
            attr[ATTR_VIBRATIONSTRENGTH] = self._device.vibrationstrength
        return attr
