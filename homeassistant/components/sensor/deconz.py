"""
Support for deCONZ sensor.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.deconz/
"""
import asyncio

from homeassistant.components.deconz import DOMAIN as DECONZ_DATA
from homeassistant.const import ATTR_BATTERY_LEVEL, CONF_EVENT, CONF_ID
from homeassistant.core import EventOrigin, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util import slugify

DEPENDENCIES = ['deconz']

ATTR_EVENT_ID = 'event_id'


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the deCONZ sensors."""
    if discovery_info is None:
        return

    from pydeconz.sensor import DECONZ_SENSOR, SWITCH as DECONZ_REMOTE
    sensors = hass.data[DECONZ_DATA].sensors
    entities = []

    for key in sorted(sensors.keys(), key=int):
        sensor = sensors[key]
        if sensor and sensor.type in DECONZ_SENSOR:
            if sensor.type in DECONZ_REMOTE:
                DeconzEvent(hass, sensor)
                if sensor.battery:
                    entities.append(DeconzBattery(sensor))
            else:
                entities.append(DeconzSensor(sensor))
    async_add_devices(entities, True)


class DeconzSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, sensor):
        """Set up sensor and add update callback to get data from websocket."""
        self._sensor = sensor

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe to sensors events."""
        self._sensor.register_async_callback(self.async_update_callback)

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
        attr = {
            ATTR_BATTERY_LEVEL: self._sensor.battery,
        }
        return attr


class DeconzBattery(Entity):
    """Battery class for when a device is only represented as an event."""

    def __init__(self, device):
        """Register dispatcher callback for update of battery state."""
        self._device = device
        self._name = '{} {}'.format(self._device.name, 'Battery Level')
        self._device_class = 'battery'
        self._unit_of_measurement = "%"

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe to sensors events."""
        self._device.register_async_callback(self.async_update_callback)

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
        """Return the state attributes of the battery."""
        attr = {
            ATTR_EVENT_ID: slugify(self._device.name),
        }
        return attr


class DeconzEvent(object):
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, hass, device):
        """Register callback that will be used for signals."""
        self._hass = hass
        self._device = device
        self._device.register_async_callback(self.async_update_callback)
        self._event = 'deconz_{}'.format(CONF_EVENT)
        self._id = slugify(self._device.name)

    @callback
    def async_update_callback(self, reason):
        """Fire the event if reason is that state is updated."""
        if reason['state']:
            data = {CONF_ID: self._id, CONF_EVENT: self._device.state}
            self._hass.bus.async_fire(self._event, data, EventOrigin.remote)
