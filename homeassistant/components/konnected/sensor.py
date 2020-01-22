"""Support for DHT and DS18B20 sensors attached to a Konnected device."""
import logging

from homeassistant.const import (
    CONF_DEVICES,
    CONF_NAME,
    CONF_SENSORS,
    CONF_TYPE,
    CONF_ZONE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN as KONNECTED_DOMAIN, SIGNAL_DS18B20_NEW, SIGNAL_SENSOR_UPDATE

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    DEVICE_CLASS_TEMPERATURE: ["Temperature", TEMP_CELSIUS],
    DEVICE_CLASS_HUMIDITY: ["Humidity", "%"],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors attached to a Konnected device from a config entry."""
    data = hass.data[KONNECTED_DOMAIN]
    device_id = config_entry.data["id"]
    sensors = []

    # Initialize all DHT sensors.
    dht_sensors = [
        sensor
        for sensor in data[CONF_DEVICES][device_id][CONF_SENSORS]
        if sensor[CONF_TYPE] == "dht"
    ]
    for sensor in dht_sensors:
        sensors.append(KonnectedSensor(device_id, sensor, DEVICE_CLASS_TEMPERATURE))
        sensors.append(KonnectedSensor(device_id, sensor, DEVICE_CLASS_HUMIDITY))

    async_add_entities(sensors)

    @callback
    def async_add_ds18b20(attrs):
        """Add new KonnectedSensor representing a ds18b20 sensor."""
        sensor_config = next(
            (
                s
                for s in data[CONF_DEVICES][device_id][CONF_SENSORS]
                if s[CONF_TYPE] == "ds18b20" and s[CONF_ZONE] == attrs.get(CONF_ZONE)
            ),
            None,
        )

        async_add_entities(
            [
                KonnectedSensor(
                    device_id,
                    sensor_config,
                    DEVICE_CLASS_TEMPERATURE,
                    addr=attrs.get("addr"),
                    initial_state=attrs.get("temp"),
                )
            ],
            True,
        )

    # DS18B20 sensors entities are initialized when they report for the first
    # time. Set up a listener for that signal from the Konnected component.
    async_dispatcher_connect(hass, SIGNAL_DS18B20_NEW, async_add_ds18b20)


class KonnectedSensor(Entity):
    """Represents a Konnected DHT Sensor."""

    def __init__(self, device_id, data, sensor_type, addr=None, initial_state=None):
        """Initialize the entity for a single sensor_type."""
        self._addr = addr
        self._data = data
        self._device_id = device_id
        self._type = sensor_type
        self._zone_num = self._data.get(CONF_ZONE)
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._unique_id = addr or "{}-{}-{}".format(
            device_id, self._zone_num, sensor_type
        )

        # set initial state if known at initialization
        self._state = initial_state
        if self._state:
            self._state = round(float(self._state), 1)

        # set entity name if given
        self._name = self._data.get(CONF_NAME)
        if self._name:
            self._name += f" {SENSOR_TYPES[sensor_type][0]}"

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
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(KONNECTED_DOMAIN, self._device_id)},
        }

    async def async_added_to_hass(self):
        """Store entity_id and register state change callback."""
        entity_id_key = self._addr or self._type
        self._data[entity_id_key] = self.entity_id
        async_dispatcher_connect(
            self.hass, SIGNAL_SENSOR_UPDATE.format(self.entity_id), self.async_set_state
        )

    @callback
    def async_set_state(self, state):
        """Update the sensor's state."""
        if self._type == DEVICE_CLASS_HUMIDITY:
            self._state = int(float(state))
        else:
            self._state = round(float(state), 1)
        self.async_schedule_update_ha_state()
