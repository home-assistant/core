"""Support for the Subaru sensors."""
import logging

from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util.distance import convert
from homeassistant.util.temperature import celsius_to_fahrenheit

from . import DOMAIN as SUBARU_DOMAIN, SubaruDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Subaru binary_sensors by config_entry."""
    controller = hass.data[SUBARU_DOMAIN][config_entry.entry_id]["controller"]
    entities = []
    for device in hass.data[SUBARU_DOMAIN][config_entry.entry_id]["devices"]["sensor"]:
        entities.append(SubaruSensor(device, controller, config_entry))
    async_add_entities(entities, True)


class SubaruSensor(SubaruDevice, Entity):
    """Representation of Subaru sensors."""

    def __init__(self, subaru_device, controller, config_entry, sensor_type=None):
        """Initialize of the sensor."""
        self.current_value = None
        self.units = None
        self.last_changed_time = None
        self.type = sensor_type
        super().__init__(subaru_device, controller, config_entry)

        if self.type:
            self._name = f"{self.subaru_device.name} ({self.type})"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self.type:
            return f"{self.subaru_id}_{self.type}"
        return self.subaru_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return self.units

    async def async_update(self):
        """Update the state from the sensor."""
        _LOGGER.debug("Updating sensor: %s", self._name)
        await super().async_update()
        units = self.subaru_device.measurement

        if self.subaru_device.type == "External Temp":
            self.current_value = self.subaru_device.get_outside_temp()
            if units == "F":
                self.units = TEMP_FAHRENHEIT
                self.current_value = round(celsius_to_fahrenheit(self.current_value), 2)
            else:
                self.units = TEMP_CELSIUS
        elif self.subaru_device.type == "Odometer":
            self.current_value = self.subaru_device.get_value()
            if units == "LENGTH_MILES":
                self.units = LENGTH_MILES
                self.current_value = round(
                    convert(self.current_value, LENGTH_METERS, LENGTH_MILES), 2
                )
            else:
                self.units = LENGTH_KILOMETERS
                self.current_value = round(
                    convert(self.current_value, LENGTH_METERS, LENGTH_KILOMETERS), 2
                )
        elif self.subaru_device.type == "EV Range":
            self.current_value = self.subaru_device.get_value()
            if units == "LENGTH_MILES":
                self.units = LENGTH_MILES
            else:
                self.units = LENGTH_KILOMETERS
                self.current_value = round(
                    convert(self.current_value, LENGTH_MILES, LENGTH_KILOMETERS), 2
                )
        elif self.subaru_device.type == "Range":
            self.current_value = self.subaru_device.get_value()
            if units == "LENGTH_MILES":
                self.units = LENGTH_MILES
            else:
                self.units = LENGTH_KILOMETERS
                self.current_value = round(
                    convert(self.current_value, LENGTH_MILES, LENGTH_KILOMETERS), 2
                )
        elif self.subaru_device.type == "EV Charge Rate":
            self.units = units
            self._attributes = {
                "time_left": self.subaru_device.time_left,
            }
        else:
            self.current_value = self.subaru_device.get_value()
            self.units = units
