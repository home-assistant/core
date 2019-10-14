"""Support for Gardena sensors."""
import logging

from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
from homeassistant.const import ATTR_BATTERY_LEVEL

from . import (
    ATTR_BATTERY_STATE,
    ATTR_RF_LINK_LEVEL,
    ATTR_RF_LINK_STATE,
    ATTR_SERIAL,
    GARDENA_LOCATION,
)


_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "ambient_temperature": [TEMP_CELSIUS, "mdi:thermometer", DEVICE_CLASS_TEMPERATURE],
    "soil_temperature": [TEMP_CELSIUS, "mdi:thermometer", DEVICE_CLASS_TEMPERATURE],
    "soil_humidity": ["%", "mdi:water-percent", DEVICE_CLASS_HUMIDITY],
    "light_intensity": ["lx", None, DEVICE_CLASS_ILLUMINANCE],
}


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Gardena sensor devices."""
    dev = []
    for sensor in hass.data[GARDENA_LOCATION].find_device_by_type("SENSOR"):
        for sensor_type in SENSOR_TYPES:
            dev.append(GardenaSensor(sensor, sensor_type))
    _LOGGER.debug("Adding sensor as sensor %s", dev)
    add_entities(dev, True)


class GardenaSensor(Entity):
    """Representation of a Gardena Sensor."""

    def __init__(self, device, data_key):
        """Initialize the Gardena Sensor."""
        self._data_key = data_key
        self._name = f"Gardena {data_key.replace('_', ' ')} {device.name}"
        self._unique_id = f"{device.serial}-{device.id}-{data_key}"
        self._device = device

    async def async_added_to_hass(self):
        """Subscribe to sensor events."""
        self._device.add_callback(self.async_update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a sensor."""
        return False

    @callback
    def async_update_callback(self, device):
        """Call update for Home Assistant when the device is updated."""
        self.schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return SENSOR_TYPES.get(self._data_key)[1]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES.get(self._data_key)[0]

    @property
    def device_class(self):
        """Return the device class of this entity."""
        if self._data_key in SENSOR_TYPES:
            return SENSOR_TYPES.get(self._data_key)[2]
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self._device, self._data_key)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_BATTERY_LEVEL: self._device.battery_level,
            ATTR_BATTERY_STATE: self._device.battery_state,
            ATTR_RF_LINK_LEVEL: self._device.rf_link_level,
            ATTR_RF_LINK_STATE: self._device.rf_link_state,
            ATTR_SERIAL: self._device.serial,
        }
