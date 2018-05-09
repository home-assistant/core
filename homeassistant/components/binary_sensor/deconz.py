"""
Support for deCONZ binary sensor.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.deconz/
"""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.deconz import (
    DOMAIN as DATA_DECONZ, DATA_DECONZ_ID, DATA_DECONZ_UNSUB)
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

DEPENDENCIES = ['deconz']


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Old way of setting up deCONZ binary sensors."""
    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the deCONZ binary sensor."""
    @callback
    def async_add_sensor(sensors):
        """Add binary sensor from deCONZ."""
        from pydeconz.sensor import DECONZ_BINARY_SENSOR
        entities = []
        for sensor in sensors:
            if sensor.type in DECONZ_BINARY_SENSOR:
                entities.append(DeconzBinarySensor(sensor))
        async_add_devices(entities, True)
    hass.data[DATA_DECONZ_UNSUB].append(
        async_dispatcher_connect(hass, 'deconz_new_sensor', async_add_sensor))

    async_add_sensor(hass.data[DATA_DECONZ].sensors.values())


class DeconzBinarySensor(BinarySensorDevice):
    """Representation of a binary sensor."""

    def __init__(self, sensor):
        """Set up sensor and add update callback to get data from websocket."""
        self._sensor = sensor

    async def async_added_to_hass(self):
        """Subscribe sensors events."""
        self._sensor.register_async_callback(self.async_update_callback)
        self.hass.data[DATA_DECONZ_ID][self.entity_id] = self._sensor.deconz_id

    @callback
    def async_update_callback(self, reason):
        """Update the sensor's state.

        If reason is that state is updated,
        or reachable has changed or battery has changed.
        """
        if reason['state'] or \
           'reachable' in reason['attr'] or \
           'battery' in reason['attr']:
            self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._sensor.is_tripped

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._sensor.name

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return self._sensor.uniqueid

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._sensor.sensor_class

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._sensor.sensor_icon

    @property
    def available(self):
        """Return True if sensor is available."""
        return self._sensor.reachable

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        from pydeconz.sensor import PRESENCE
        attr = {}
        if self._sensor.battery:
            attr[ATTR_BATTERY_LEVEL] = self._sensor.battery
        if self._sensor.type in PRESENCE and self._sensor.dark:
            attr['dark'] = self._sensor.dark
        return attr
