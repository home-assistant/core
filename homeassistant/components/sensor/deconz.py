"""
Support for deCONZ sensor.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.deconz/
"""
from homeassistant.components.deconz.const import (
    ATTR_DARK, ATTR_ON, CONF_ALLOW_CLIP_SENSOR, DOMAIN as DATA_DECONZ,
    DATA_DECONZ_ID, DATA_DECONZ_UNSUB)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_VOLTAGE, DEVICE_CLASS_BATTERY)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

DEPENDENCIES = ['deconz']

ATTR_CURRENT = 'current'
ATTR_DAYLIGHT = 'daylight'
ATTR_EVENT_ID = 'event_id'


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Old way of setting up deCONZ sensors."""
    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the deCONZ sensors."""
    @callback
    def async_add_sensor(sensors):
        """Add sensors from deCONZ."""
        from pydeconz.sensor import DECONZ_SENSOR, SWITCH as DECONZ_REMOTE
        entities = []
        allow_clip_sensor = config_entry.data.get(CONF_ALLOW_CLIP_SENSOR, True)
        for sensor in sensors:
            if sensor.type in DECONZ_SENSOR and \
               not (not allow_clip_sensor and sensor.type.startswith('CLIP')):
                if sensor.type in DECONZ_REMOTE:
                    if sensor.battery:
                        entities.append(DeconzBattery(sensor))
                else:
                    entities.append(DeconzSensor(sensor))
        async_add_devices(entities, True)

    hass.data[DATA_DECONZ_UNSUB].append(
        async_dispatcher_connect(hass, 'deconz_new_sensor', async_add_sensor))

    async_add_sensor(hass.data[DATA_DECONZ].sensors.values())


class DeconzSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, sensor):
        """Set up sensor and add update callback to get data from websocket."""
        self._sensor = sensor

    async def async_added_to_hass(self):
        """Subscribe to sensors events."""
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
           'battery' in reason['attr'] or \
           'on' in reason['attr']:
            self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._sensor.state

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
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return self._sensor.sensor_unit

    @property
    def available(self):
        """Return true if sensor is available."""
        return self._sensor.reachable

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        from pydeconz.sensor import LIGHTLEVEL
        attr = {}
        if self._sensor.battery:
            attr[ATTR_BATTERY_LEVEL] = self._sensor.battery
        if self._sensor.on is not None:
            attr[ATTR_ON] = self._sensor.on
        if self._sensor.type in LIGHTLEVEL and self._sensor.dark is not None:
            attr[ATTR_DARK] = self._sensor.dark
        if self.unit_of_measurement == 'Watts':
            attr[ATTR_CURRENT] = self._sensor.current
            attr[ATTR_VOLTAGE] = self._sensor.voltage
        if self._sensor.sensor_class == 'daylight':
            attr[ATTR_DAYLIGHT] = self._sensor.daylight
        return attr


class DeconzBattery(Entity):
    """Battery class for when a device is only represented as an event."""

    def __init__(self, device):
        """Register dispatcher callback for update of battery state."""
        self._device = device
        self._name = '{} {}'.format(self._device.name, 'Battery Level')
        self._unit_of_measurement = "%"

    async def async_added_to_hass(self):
        """Subscribe to sensors events."""
        self._device.register_async_callback(self.async_update_callback)
        self.hass.data[DATA_DECONZ_ID][self.entity_id] = self._device.deconz_id

    @callback
    def async_update_callback(self, reason):
        """Update the battery's state, if needed."""
        if 'battery' in reason['attr']:
            self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the battery."""
        return self._device.battery

    @property
    def name(self):
        """Return the name of the battery."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for the device."""
        return self._device.uniqueid

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return DEVICE_CLASS_BATTERY

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
        """Return the state attributes of the battery."""
        attr = {
            ATTR_EVENT_ID: slugify(self._device.name),
        }
        return attr
