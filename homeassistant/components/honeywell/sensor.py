"""Support for Honeywell (US) Total Connect Comfort sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

from .const import DOMAIN


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the Honeywell thermostat."""
    data = hass.data[DOMAIN][config.entry_id]
    sensors = []

    for device in data.devices.values():
        if device.outdoor_temperature is not None:
            sensors.append(HoneywellOutdoorTemperatureSensor(device))
        if device.outdoor_humidity is not None:
            sensors.append(HoneywellOutdoorHumiditySensor(device))

    async_add_entities(sensors)


class HoneywellOutdoorTemperatureSensor(SensorEntity):
    """Representation of a Honeywell US Outdoor Temperature Sensor."""

    def __init__(self, device):
        """Initialize the outdoor temperature sensor."""
        self._device = device
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{device.deviceid}_outdoor_{DEVICE_CLASS_TEMPERATURE}"
        self._attr_name = f"{device.name} outdoor {DEVICE_CLASS_TEMPERATURE}"
        self._attr_device_class = DEVICE_CLASS_TEMPERATURE
        self._attr_native_unit_of_measurement = (
            TEMP_CELSIUS if self._device.temperature_unit == "C" else TEMP_FAHRENHEIT
        )

    def update(self):
        """Get the latest state from the service."""
        self._attr_native_value = self._device.outdoor_temperature


class HoneywellOutdoorHumiditySensor(SensorEntity):
    """Representation of a Honeywell US Outdoor Humidity Sensor."""

    def __init__(self, device):
        """Initialize the outdoor humidity sensor."""
        self._device = device
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{device.deviceid}_outdoor_{DEVICE_CLASS_HUMIDITY}"
        self._attr_name = f"{device.name} outdoor {DEVICE_CLASS_HUMIDITY}"
        self._attr_device_class = DEVICE_CLASS_HUMIDITY
        self._attr_native_unit_of_measurement = PERCENTAGE

    def update(self):
        """Get the latest state from the service."""
        self._attr_native_value = self._device.outdoor_humidity
