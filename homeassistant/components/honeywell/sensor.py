"""Support for Honeywell (US) Total Connect Comfort sensors."""
from __future__ import annotations

import logging

import homeassistant
from homeassistant.components.honeywell.const import DOMAIN
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, config, async_add_entities, discovery_info=None
) -> None:
    """Set up the Honeywell thermostat."""
    data = hass.data[DOMAIN]
    sensors = []

    if data._device.current_temperature is not None:
        sensors.append(HoneywellUSSensor(data, "indoor", "temperature"))
    if (
        data._device.current_humidity is not None
        and data._device.current_humidity != 128
    ):
        sensors.append(HoneywellUSSensor(data, "indoor", "humidity"))
    if data._device.outdoor_temperature is not None:
        sensors.append(HoneywellUSSensor(data, "outdoor", "temperature"))
    if data._device.outdoor_humidity is not None:
        sensors.append(HoneywellUSSensor(data, "outdoor", "humidity"))

    async_add_entities(sensors)

    return True


class HoneywellUSSensor(SensorEntity):
    """Representation of a Honeywell US Sensor."""

    def __init__(self, data, location, sensor_type):
        """Initialize the sensor."""
        self._data = data

        self._name = f"{data._device.name} {location} {sensor_type}"
        self._location = location
        self._type = sensor_type

        _LOGGER.debug("latestData = %s ", data._device._data)

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{homeassistant.helpers.device_registry.format_mac(self._data._device.mac_address)}_{self._name}"

    @property
    def name(self):
        """Return the name of the Honeywell US Sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self._type in (DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE):
            return self._type
        return None

    @property
    def state(self):
        """Return the state of the sensor."""

        if self._type == "temperature":
            return self.temperature

        return self.humidity

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        if self._type == "temperature":
            return (
                TEMP_CELSIUS
                if self._data._device.temperature_unit == "C"
                else TEMP_FAHRENHEIT
            )

        return PERCENTAGE

    @property
    def humidity(self) -> int | None:
        """Return the current outdoor humidity."""
        if self._location == "indoor":
            return self._data._device.current_humidity
        return self._data._device.outdoor_humidity

    @property
    def temperature(self) -> float | None:
        """Return the current outdoor temperature."""
        if self._location == "indoor":
            return self._data._device.current_temperature
        return self._data._device.outdoor_temperature

    async def async_update(self):
        """Get the latest state of the sensor."""
        await self._data.update()
