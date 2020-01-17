"""Support for SimpliSafe binary sensors."""
import logging

from simplipy.entity import EntityTypes

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import ATTR_TEMPERATURE

from . import SimpliSafeEntity
from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_SENSOR_TYPE = "sensor_type"
ATTR_ERROR_STATE = "error_state"
ATTR_LOW_BATTERY = "low_battery"
ATTR_TRIGGER_INSTANTLY = "trigger_instantly"

BINARY_SENSOR_TYPES = {
    EntityTypes.carbon_monoxide: "smoke",
    EntityTypes.entry: "door",
    EntityTypes.glass_break: "safety",
    EntityTypes.leak: "moisture",
    EntityTypes.motion: "motion",
    EntityTypes.smoke: "smoke",
    EntityTypes.temperature: "cold",
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SimpliSafe locks based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    async_add_entities(
        [
            SimpliSafeBinarySensor(system, sensor, BINARY_SENSOR_TYPES[sensor.type])
            for system in simplisafe.systems.values()
            for sensor in system.sensors.values()
            if sensor.type in BINARY_SENSOR_TYPES
        ],
        True,
    )


class SimpliSafeBinarySensor(SimpliSafeEntity, BinarySensorDevice):
    """A sensor implementation for raincloud device."""

    def __init__(self, system, sensor, device_class):
        """Initialize."""
        super().__init__(system, sensor.name, serial=sensor.serial)
        self._device_class = device_class
        self._is_on = False
        self._sensor = sensor

        self._attrs.update({ATTR_SENSOR_TYPE: sensor.type.name})

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._is_on

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    async def async_update(self):
        """Update lock status."""
        if getattr(self._sensor, "offline", False) and self._sensor.offline:
            self._online = False
            return

        self._online = True

        self._is_on = self._sensor.triggered

        self._attrs.update(
            {
                ATTR_ERROR_STATE: self._sensor.error,
                ATTR_LOW_BATTERY: self._sensor.low_battery,
                ATTR_TRIGGER_INSTANTLY: self._sensor.trigger_instantly,
            }
        )
        if self._sensor.type == EntityTypes.temperature:
            self._attrs[ATTR_TEMPERATURE] = self._sensor.temperature
