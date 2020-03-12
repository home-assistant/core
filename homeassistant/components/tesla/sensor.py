"""Support for the Tesla sensors."""
import logging

from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util.distance import convert

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Tesla binary_sensors by config_entry."""
    controller = hass.data[TESLA_DOMAIN][config_entry.entry_id]["controller"]
    entities = []
    for device in hass.data[TESLA_DOMAIN][config_entry.entry_id]["devices"]["sensor"]:
        if device.type == "temperature sensor":
            entities.append(TeslaSensor(device, controller, config_entry, "inside"))
            entities.append(TeslaSensor(device, controller, config_entry, "outside"))
        else:
            entities.append(TeslaSensor(device, controller, config_entry))
    async_add_entities(entities, True)


class TeslaSensor(TeslaDevice, Entity):
    """Representation of Tesla sensors."""

    def __init__(self, tesla_device, controller, config_entry, sensor_type=None):
        """Initialize of the sensor."""
        self.current_value = None
        self.units = None
        self.last_changed_time = None
        self.type = sensor_type
        self._device_class = tesla_device.device_class
        super().__init__(tesla_device, controller, config_entry)

        if self.type:
            self._name = f"{self.tesla_device.name} ({self.type})"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self.type:
            return f"{self.tesla_id}_{self.type}"
        return self.tesla_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return self.units

    @property
    def device_class(self):
        """Return the device_class of the device."""
        return self._device_class

    async def async_update(self):
        """Update the state from the sensor."""
        _LOGGER.debug("Updating sensor: %s", self._name)
        await super().async_update()
        units = self.tesla_device.measurement

        if self.tesla_device.type == "temperature sensor":
            if self.type == "outside":
                self.current_value = self.tesla_device.get_outside_temp()
            else:
                self.current_value = self.tesla_device.get_inside_temp()
            if units == "F":
                self.units = TEMP_FAHRENHEIT
            else:
                self.units = TEMP_CELSIUS
        elif self.tesla_device.type in ["range sensor", "mileage sensor"]:
            self.current_value = self.tesla_device.get_value()
            if units == "LENGTH_MILES":
                self.units = LENGTH_MILES
            else:
                self.units = LENGTH_KILOMETERS
                self.current_value = round(
                    convert(self.current_value, LENGTH_MILES, LENGTH_KILOMETERS), 2
                )
        elif self.tesla_device.type == "charging rate sensor":
            self.current_value = self.tesla_device.charging_rate
            self.units = units
            self._attributes = {
                "time_left": self.tesla_device.time_left,
                "added_range": self.tesla_device.added_range,
                "charge_energy_added": self.tesla_device.charge_energy_added,
                "charge_current_request": self.tesla_device.charge_current_request,
                "charger_actual_current": self.tesla_device.charger_actual_current,
                "charger_voltage": self.tesla_device.charger_voltage,
            }
        else:
            self.current_value = self.tesla_device.get_value()
            self.units = units
