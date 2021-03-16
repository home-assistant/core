"""Support for a ScreenLogic Binary Sensor."""
import logging

from screenlogicpy.const import ON_OFF

from homeassistant.components.binary_sensor import DEVICE_CLASSES, BinarySensorEntity

from . import ScreenlogicEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]

    for binary_sensor in data["devices"]["binary_sensor"]:
        entities.append(ScreenLogicBinarySensor(coordinator, binary_sensor))
    async_add_entities(entities, True)


class ScreenLogicBinarySensor(ScreenlogicEntity, BinarySensorEntity):
    """Representation of a ScreenLogic binary sensor entity."""

    @property
    def name(self):
        """Return the sensor name."""
        return f"{self.gateway_name} {self.sensor['name']}"

    @property
    def device_class(self):
        """Return the device class."""
        device_class = self.sensor.get("hass_type")
        if device_class in DEVICE_CLASSES:
            return device_class
        return None

    @property
    def is_on(self) -> bool:
        """Determine if the sensor is on."""
        return self.sensor["value"] == ON_OFF.ON

    @property
    def sensor(self):
        """Shortcut to access the sensor data."""
        return self.sensor_data[self._data_key]

    @property
    def sensor_data(self):
        """Shortcut to access the sensors data."""
        return self.coordinator.data["sensors"]
