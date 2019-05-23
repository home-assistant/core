"""Support for deCONZ binary sensors."""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import ATTR_DARK, ATTR_ON, NEW_SENSOR
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry

ATTR_ORIENTATION = 'orientation'
ATTR_TILTANGLE = 'tiltangle'
ATTR_VIBRATIONSTRENGTH = 'vibrationstrength'


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the deCONZ binary sensor."""
    gateway = get_gateway_from_config_entry(hass, config_entry)

    @callback
    def async_add_sensor(sensors):
        """Add binary sensor from deCONZ."""
        entities = []

        for sensor in sensors:

            if sensor.BINARY and \
               not (not gateway.allow_clip_sensor and
                    sensor.type.startswith('CLIP')):

                entities.append(DeconzBinarySensor(sensor, gateway))

        async_add_entities(entities, True)

    gateway.listeners.append(async_dispatcher_connect(
        hass, gateway.async_event_new_device(NEW_SENSOR), async_add_sensor))

    async_add_sensor(gateway.api.sensors.values())


class DeconzBinarySensor(DeconzDevice, BinarySensorDevice):
    """Representation of a deCONZ binary sensor."""

    @callback
    def async_update_callback(self, force_update=False):
        """Update the sensor's state."""
        changed = self._device.changed_keys
        if force_update or 'state' in changed or 'reachable' in changed or \
           'battery' in changed or 'on' in changed:
            self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._device.is_tripped

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device.SENSOR_CLASS

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._device.SENSOR_ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        from pydeconz.sensor import Presence, Vibration

        attr = {}
        if self._device.battery:
            attr[ATTR_BATTERY_LEVEL] = self._device.battery

        if self._device.on is not None:
            attr[ATTR_ON] = self._device.on

        if self._device.type in Presence.ZHATYPE and \
                self._device.dark is not None:
            attr[ATTR_DARK] = self._device.dark
        elif self._device.type in Vibration.ZHATYPE:
            attr[ATTR_ORIENTATION] = self._device.orientation
            attr[ATTR_TILTANGLE] = self._device.tiltangle
            attr[ATTR_VIBRATIONSTRENGTH] = self._device.vibrationstrength

        return attr
