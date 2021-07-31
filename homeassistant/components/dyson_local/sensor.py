"""Sensor platform for dyson."""

from typing import Callable

from libdyson import DysonDevice
from libdyson.const import MessageType

from homeassistant.components.sensor import DEVICE_CLASS_BATTERY
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant

from . import DysonEntity
from .const import DATA_DEVICES, DOMAIN

SENSORS = {
    "battery_level": (
        "Battery Level",
        {
            ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        },
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Dyson sensor from a config entry."""
    device = hass.data[DOMAIN][DATA_DEVICES][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]
    entities = [DysonBatterySensor(device, name)]
    async_add_entities(entities)


class DysonSensor(DysonEntity):
    """Generic Dyson sensor."""

    _MESSAGE_TYPE = MessageType.STATE
    _SENSOR_TYPE: str

    def __init__(self, device: DysonDevice, name: str) -> None:
        """Initialize the sensor."""
        super().__init__(device, name)
        self._old_value = None
        self._sensor_name, self._attributes = SENSORS[self._SENSOR_TYPE]

    @property
    def sub_name(self):
        """Return the name of the Dyson sensor."""
        return self._sensor_name

    @property
    def sub_unique_id(self):
        """Return the sensor's unique id."""
        return self._SENSOR_TYPE

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._attributes.get(ATTR_UNIT_OF_MEASUREMENT)

    @property
    def icon(self):
        """Return the icon for this sensor."""
        return self._attributes.get(ATTR_ICON)

    @property
    def device_class(self):
        """Return the device class of this sensor."""
        return self._attributes.get(ATTR_DEVICE_CLASS)


class DysonBatterySensor(DysonSensor):
    """Dyson battery sensor."""

    _SENSOR_TYPE = "battery_level"

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self._device.battery_level
