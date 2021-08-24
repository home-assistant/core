"""Support for Gardena Smart System sensors."""
import logging

from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    DEVICE_CLASS_BATTERY,
    PERCENTAGE,
)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    DOMAIN,
    ATTR_BATTERY_STATE,
    ATTR_RF_LINK_LEVEL,
    ATTR_RF_LINK_STATE,
    ATTR_SERIAL,
    GARDENA_LOCATION,
)

_LOGGER = logging.getLogger(__name__)

SOIL_SENSOR_TYPES = {
    "soil_temperature": [TEMP_CELSIUS, "mdi:thermometer", DEVICE_CLASS_TEMPERATURE],
    "soil_humidity": ["%", "mdi:water-percent", DEVICE_CLASS_HUMIDITY],
    ATTR_BATTERY_LEVEL: [PERCENTAGE, "mdi:battery", DEVICE_CLASS_BATTERY],
}

SENSOR_TYPES = {**{
    "ambient_temperature": [TEMP_CELSIUS, "mdi:thermometer", DEVICE_CLASS_TEMPERATURE],
    "light_intensity": ["lx", None, DEVICE_CLASS_ILLUMINANCE],
}, **SOIL_SENSOR_TYPES}

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Gardena sensor devices."""
    entities = []
    for sensor in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type("SENSOR"):
        for sensor_type in SENSOR_TYPES:
            entities.append(GardenaSensor(sensor, sensor_type))

    for sensor in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type("SOIL_SENSOR"):
        for sensor_type in SOIL_SENSOR_TYPES:
            entities.append(GardenaSensor(sensor, sensor_type))

    for mower in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type("MOWER"):
        # Add battery sensor for mower
        entities.append(GardenaSensor(mower, ATTR_BATTERY_LEVEL))

    for water_control in hass.data[DOMAIN][GARDENA_LOCATION].find_device_by_type("WATER_CONTROL"):
        # Add battery sensor for water control
        entities.append(GardenaSensor(water_control, ATTR_BATTERY_LEVEL))
    _LOGGER.debug("Adding sensor as sensor %s", entities)
    async_add_entities(entities, True)


class GardenaSensor(Entity):
    """Representation of a Gardena Sensor."""

    def __init__(self, device, sensor_type):
        """Initialize the Gardena Sensor."""
        self._sensor_type = sensor_type
        self._name = f"{device.name} {sensor_type.replace('_', ' ')}"
        self._unique_id = f"{device.serial}-{sensor_type}"
        self._device = device

    async def async_added_to_hass(self):
        """Subscribe to sensor events."""
        self._device.add_callback(self.update_callback)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a sensor."""
        return False

    def update_callback(self, device):
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
        return SENSOR_TYPES[self._sensor_type][1]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self._sensor_type][0]

    @property
    def device_class(self):
        """Return the device class of this entity."""
        if self._sensor_type in SENSOR_TYPES:
            return SENSOR_TYPES[self._sensor_type][2]
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self._device, self._sensor_type)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_BATTERY_LEVEL: self._device.battery_level,
            ATTR_BATTERY_STATE: self._device.battery_state,
            ATTR_RF_LINK_LEVEL: self._device.rf_link_level,
            ATTR_RF_LINK_STATE: self._device.rf_link_state,
        }

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._device.serial)
            },
            "name": self._device.name,
            "manufacturer": "Gardena",
            "model": self._device.model_type,
        }
