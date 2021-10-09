"""Support for Honeywell (US) Total Connect Comfort sensors."""
from __future__ import annotations

from homeassistant.components.honeywell.const import DOMAIN
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the Honeywell thermostat."""
    data = hass.data[DOMAIN][config.entry_id]
    sensors = []

    for device in data.devices:
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
        self._state = None
        self._attr_unique_id = f"{device.deviceid}_outdoor_{DEVICE_CLASS_TEMPERATURE}"
        self._attr_name = f"{device.name} outdoor {DEVICE_CLASS_TEMPERATURE}"
        self._attr_device_class = DEVICE_CLASS_TEMPERATURE

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return TEMP_CELSIUS if self._device.temperature_unit == "C" else TEMP_FAHRENHEIT

    def update(self):
        """Get the latest state from the service."""
        self._state = self._device.outdoor_temperature


class HoneywellOutdoorHumiditySensor(SensorEntity):
    """Representation of a Honeywell US Outdoor Humidity Sensor."""

    def __init__(self, device):
        """Initialize the outdoor humidity sensor."""
        self._device = device
        self._state = None
        self._attr_unique_id = f"{device.deviceid}_outdoor_{DEVICE_CLASS_HUMIDITY}"
        self._attr_name = f"{device.name} outdoor {DEVICE_CLASS_HUMIDITY}"
        self._attr_device_class = DEVICE_CLASS_HUMIDITY

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return PERCENTAGE

    def update(self):
        """Get the latest state from the service."""
        self._state = self._device.outdoor_humidity
