"""Support for the Tesla sensors."""
from __future__ import annotations

from homeassistant.components.sensor import DEVICE_CLASSES, SensorEntity
from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.util.distance import convert

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice


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


class TeslaSensor(TeslaDevice, SensorEntity):
    """Representation of Tesla sensors."""

    def __init__(self, tesla_device, coordinator, sensor_type=None):
        """Initialize of the sensor."""
        super().__init__(tesla_device, coordinator)
        self.type = sensor_type
        if self.type:
            self._name = f"{super().name} ({self.type})"
            self._unique_id = f"{super().unique_id}_{self.type}"

    @property
    def state(self) -> float | None:
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
    def unit_of_measurement(self) -> str | None:
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
    def device_class(self) -> str | None:
        """Return the device_class of the device."""
        return (
            self.tesla_device.device_class
            if self.tesla_device.device_class in DEVICE_CLASSES
            else None
        )

    @property
    def extra_state_attributes(self):
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
