"""Support for DHT and DS18B20 sensors attached to a Konnected device."""
import logging

from homeassistant.components.konnected import (
    DOMAIN as KONNECTED_DOMAIN, SIGNAL_DS18B20_NEW, SIGNAL_SENSOR_UPDATE)
from homeassistant.const import (
    CONF_DEVICES, CONF_PIN, CONF_TYPE, CONF_NAME, CONF_SENSORS,
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE, TEMP_FAHRENHEIT)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.util.temperature import celsius_to_fahrenheit

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['konnected']

SENSOR_TYPES = {
    DEVICE_CLASS_TEMPERATURE: ['Temperature', None],
    DEVICE_CLASS_HUMIDITY: ['Humidity', '%']
}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up sensors attached to a Konnected device."""
    if discovery_info is None:
        return

    SENSOR_TYPES[DEVICE_CLASS_TEMPERATURE][1] = \
        hass.config.units.temperature_unit

    data = hass.data[KONNECTED_DOMAIN]
    device_id = discovery_info['device_id']
    sensors = []

    # Initialize all DHT sensors.
    dht_sensors = [sensor for sensor
                   in data[CONF_DEVICES][device_id][CONF_SENSORS]
                   if sensor[CONF_TYPE] == 'dht']
    for sensor in dht_sensors:
        sensors.append(
            KonnectedSensor(device_id, sensor, DEVICE_CLASS_TEMPERATURE))
        sensors.append(
            KonnectedSensor(device_id, sensor, DEVICE_CLASS_HUMIDITY))

    async_add_entities(sensors)

    @callback
    def async_add_ds18b20(data):
        """Add new KonnectedSensor representing a ds18b20 sensor."""
        async_add_entities([
            KonnectedSensor(data.get('device_id'), data,
                            DEVICE_CLASS_TEMPERATURE)
        ], True)

    # DS18B20 sensors entities are initialized when they report for the first
    # time. Set up a listener for that signal from the Konnected component.
    async_dispatcher_connect(hass, SIGNAL_DS18B20_NEW, async_add_ds18b20)


class KonnectedSensor(Entity):
    """Represents a Konnected DHT Sensor."""

    def __init__(self, device_id, data, sensor_type):
        """Initialize the entity for a single sensor_type."""
        self._data = data
        self._device_id = device_id
        self._type = sensor_type
        self._pin_num = self._data.get(CONF_PIN)
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._state = None
        self._name = self._data.get(CONF_NAME)
        if self._name:
            self._name += ' ' + SENSOR_TYPES[sensor_type][0]
        self._unique_id = '{}-{}-{}'.format(
            device_id, self._pin_num, sensor_type)
        if sensor_type == DEVICE_CLASS_TEMPERATURE:
            self._state = self.temperature(self._data.get(sensor_type))

    def temperature(self, number=None):
        """Format temperature and convert to Fahrenheit if necessary."""
        if number is None:
            return None

        number = float(number)
        if self._unit_of_measurement == TEMP_FAHRENHEIT:
            number = celsius_to_fahrenheit(number)
        return round(number, 1)

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    async def async_added_to_hass(self):
        """Store entity_id and register state change callback."""
        entity_id_key = self._data.get('addr') or self._type
        self._data[entity_id_key] = self.entity_id
        async_dispatcher_connect(
            self.hass, SIGNAL_SENSOR_UPDATE.format(self.entity_id),
            self.async_set_state)

    @callback
    def async_set_state(self, state):
        """Update the sensor's state."""
        if self._type == DEVICE_CLASS_TEMPERATURE:
            self._state = self.temperature(state)
        else:
            self._state = int(float(state))
        self.async_schedule_update_ha_state()
