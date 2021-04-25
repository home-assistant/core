"""Support for a ScreenLogic Binary Sensor."""
import logging

from screenlogicpy.const import DATA as SL_DATA, DEVICE_TYPE, ON_OFF

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)

from . import ScreenlogicEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS = {DEVICE_TYPE.ALARM: DEVICE_CLASS_PROBLEM}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    # Generic binary sensor
    entities.append(ScreenLogicBinarySensor(coordinator, "chem_alarm"))

    async_add_entities(entities)


class ScreenLogicBinarySensor(ScreenlogicEntity, BinarySensorEntity):
    """Representation of the basic ScreenLogic binary sensor entity."""

    @property
    def name(self):
        """Return the sensor name."""
        return f"{self.gateway_name} {self.sensor['name']}"

    @property
    def device_class(self):
        """Return the device class."""
        device_class = self.sensor.get("device_type")
        return SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS.get(device_class)

    @property
    def is_on(self) -> bool:
        """Determine if the sensor is on."""
        return self.sensor["value"] == ON_OFF.ON

    @property
    def sensor(self):
        """Shortcut to access the sensor data."""
        return self.coordinator.data[SL_DATA.KEY_SENSORS][self._data_key]
