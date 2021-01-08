"""Support for Plaato Airlock sensors."""

import logging

from homeassistant.const import PERCENTAGE
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from . import (
    ATTR_ABV,
    ATTR_BATCH_VOLUME,
    ATTR_BPM,
    ATTR_CO2_VOLUME,
    ATTR_TEMP,
    ATTR_TEMP_UNIT,
    ATTR_VOLUME_UNIT,
    DOMAIN as PLAATO_DOMAIN,
    PLAATO_DEVICE_ATTRS,
    PLAATO_DEVICE_SENSORS,
    SENSOR_DATA_KEY,
    SENSOR_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Plaato sensor."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Plaato from a config entry."""
    devices = {}

    def get_device(device_id):
        """Get a device."""
        return hass.data[PLAATO_DOMAIN].get(device_id, False)

    def get_device_sensors(device_id):
        """Get device sensors."""
        return hass.data[PLAATO_DOMAIN].get(device_id).get(PLAATO_DEVICE_SENSORS)

    async def _update_sensor(device_id):
        """Update/Create the sensors."""
        if device_id not in devices and get_device(device_id):
            entities = []
            sensors = get_device_sensors(device_id)

            for sensor_type in sensors:
                entities.append(PlaatoSensor(device_id, sensor_type))

            devices[device_id] = entities

            async_add_entities(entities, True)
        else:
            for entity in devices[device_id]:
                async_dispatcher_send(hass, f"{PLAATO_DOMAIN}_{entity.unique_id}")

    hass.data[SENSOR_DATA_KEY] = async_dispatcher_connect(
        hass, SENSOR_UPDATE, _update_sensor
    )

    return True


class PlaatoSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, device_id, sensor_type):
        """Initialize the sensor."""
        self._device_id = device_id
        self._type = sensor_type
        self._state = 0
        self._name = f"{device_id} {sensor_type}"
        self._attributes = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{PLAATO_DOMAIN} {self._name}"

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return f"{self._device_id}_{self._type}"

    @property
    def device_info(self):
        """Get device info."""
        return {
            "identifiers": {(PLAATO_DOMAIN, self._device_id)},
            "name": self._device_id,
            "manufacturer": "Plaato",
            "model": "Airlock",
        }

    def get_sensors(self):
        """Get device sensors."""
        return (
            self.hass.data[PLAATO_DOMAIN]
            .get(self._device_id)
            .get(PLAATO_DEVICE_SENSORS, False)
        )

    def get_sensors_unit_of_measurement(self, sensor_type):
        """Get unit of measurement for sensor of type."""
        return (
            self.hass.data[PLAATO_DOMAIN]
            .get(self._device_id)
            .get(PLAATO_DEVICE_ATTRS, [])
            .get(sensor_type, "")
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        sensors = self.get_sensors()
        if sensors is False:
            _LOGGER.debug("Device with name %s has no sensors", self.name)
            return 0

        if self._type == ATTR_ABV:
            return round(sensors.get(self._type), 2)
        if self._type == ATTR_TEMP:
            return round(sensors.get(self._type), 1)
        if self._type == ATTR_CO2_VOLUME:
            return round(sensors.get(self._type), 2)
        return sensors.get(self._type)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the monitored installation."""
        if self._attributes is not None:
            return self._attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._type == ATTR_TEMP:
            return self.get_sensors_unit_of_measurement(ATTR_TEMP_UNIT)
        if self._type == ATTR_BATCH_VOLUME or self._type == ATTR_CO2_VOLUME:
            return self.get_sensors_unit_of_measurement(ATTR_VOLUME_UNIT)
        if self._type == ATTR_BPM:
            return "bpm"
        if self._type == ATTR_ABV:
            return PERCENTAGE

        return ""

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                f"{PLAATO_DOMAIN}_{self.unique_id}", self.async_write_ha_state
            )
        )
