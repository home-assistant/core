"""Support for the Tesla sensors."""
import logging
from typing import Optional

from homeassistant.components.sensor import DEVICE_CLASSES
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
    coordinator = hass.data[TESLA_DOMAIN][config_entry.entry_id]["coordinator"]
    entities = []
    for device in hass.data[TESLA_DOMAIN][config_entry.entry_id]["devices"]["sensor"]:
        if device.type == "temperature sensor":
            entities.append(TeslaSensor(device, coordinator, "inside"))
            entities.append(TeslaSensor(device, coordinator, "outside"))
        else:
            entities.append(TeslaSensor(device, coordinator))
    async_add_entities(entities, True)


class TeslaSensor(TeslaDevice, Entity):
    """Representation of Tesla sensors."""

    def __init__(self, tesla_device, coordinator, sensor_type=None):
        """Initialize of the sensor."""
        super().__init__(tesla_device, coordinator)
        self.type = sensor_type

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return (
            self.tesla_device.name
            if not self.type
            else f"{self.tesla_device.name} ({self.type})"
        )

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return (
            super().unique_id if not self.type else f"{super().unique_id}_{self.type}"
        )

    @property
    def state(self) -> Optional[float]:
        """Return the state of the sensor."""
        if self.tesla_device.type == "temperature sensor":
            if self.type == "outside":
                return self.tesla_device.get_outside_temp()
            return self.tesla_device.get_inside_temp()
        if self.tesla_device.type in ["range sensor", "mileage sensor"]:
            units = self.tesla_device.measurement
            if units == "LENGTH_MILES":
                return self.tesla_device.get_value()
            return round(
                convert(self.tesla_device.get_value(), LENGTH_MILES, LENGTH_KILOMETERS),
                2,
            )
        if self.tesla_device.type == "charging rate sensor":
            return self.tesla_device.charging_rate
        return self.tesla_device.get_value()

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit_of_measurement of the device."""
        units = self.tesla_device.measurement
        if units == "F":
            return TEMP_FAHRENHEIT
        if units == "C":
            return TEMP_CELSIUS
        if units == "LENGTH_MILES":
            return LENGTH_MILES
        if units == "LENGTH_KILOMETERS":
            return LENGTH_KILOMETERS
        return units

    @property
    def device_class(self) -> Optional[str]:
        """Return the device_class of the device."""
        return (
            self.tesla_device.device_class
            if self.tesla_device.device_class in DEVICE_CLASSES
            else None
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = self._attributes.copy()
        if self.tesla_device.type == "charging rate sensor":
            attr.update(
                {
                    "time_left": self.tesla_device.time_left,
                    "added_range": self.tesla_device.added_range,
                    "charge_energy_added": self.tesla_device.charge_energy_added,
                    "charge_current_request": self.tesla_device.charge_current_request,
                    "charger_actual_current": self.tesla_device.charger_actual_current,
                    "charger_voltage": self.tesla_device.charger_voltage,
                }
            )
        return attr
