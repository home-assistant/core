"""Support for Honeywell (US) Total Connect Comfort sensors."""
from __future__ import annotations

import homeassistant
from homeassistant.components.honeywell.const import (
    DOMAIN,
    SENSOR_LOCATION_INDOOR,
    SENSOR_LOCATION_OUTDOOR,
)
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)


async def async_setup_entry(
    hass, config, async_add_entities, discovery_info=None
) -> None:
    """Set up the Honeywell thermostat."""
    data = hass.data[DOMAIN][config.entry_id]
    sensors = []

    if data.device.current_temperature is not None:
        sensors.append(
            HoneywellUSSensor(data, SENSOR_LOCATION_INDOOR, DEVICE_CLASS_TEMPERATURE)
        )
    if data.device.current_humidity is not None:
        sensors.append(
            HoneywellUSSensor(data, SENSOR_LOCATION_INDOOR, DEVICE_CLASS_HUMIDITY)
        )
    if data.device.outdoor_temperature is not None:
        sensors.append(
            HoneywellUSSensor(data, SENSOR_LOCATION_OUTDOOR, DEVICE_CLASS_TEMPERATURE)
        )
    if data.device.outdoor_humidity is not None:
        sensors.append(
            HoneywellUSSensor(data, SENSOR_LOCATION_OUTDOOR, DEVICE_CLASS_HUMIDITY)
        )

    async_add_entities(sensors)

    return True


class HoneywellUSSensor(SensorEntity):
    """Representation of a Honeywell US Sensor."""

    def __init__(self, data, location, sensor_type):
        """Initialize the sensor."""
        self._data = data
        self._unique_id = f"{homeassistant.helpers.device_registry.format_mac(data.device.mac_address)}_{location}_{sensor_type}"
        self._name = f"{data.device.name} {location} {sensor_type}"
        self._location = location
        self._type = sensor_type

    @property
    def device(self):
        """Shortcut to access the device."""
        return self._data.device

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the Honeywell US Sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._type

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._type == DEVICE_CLASS_TEMPERATURE:
            return self.temperature
        if self._type == DEVICE_CLASS_HUMIDITY:
            return self.humidity

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return STATE_CLASS_MEASUREMENT

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        if self._type == DEVICE_CLASS_TEMPERATURE:
            return (
                TEMP_CELSIUS if self.device.temperature_unit == "C" else TEMP_FAHRENHEIT
            )

        return PERCENTAGE

    @property
    def humidity(self) -> int | None:
        """Return the current outdoor humidity."""
        if self._location == SENSOR_LOCATION_INDOOR:
            return self.device.current_humidity
        if self._location == SENSOR_LOCATION_OUTDOOR:
            return self.device.outdoor_humidity

    @property
    def temperature(self) -> float | None:
        """Return the current outdoor temperature."""
        if self._location == SENSOR_LOCATION_INDOOR:
            return self.device.current_temperature
        if self._location == SENSOR_LOCATION_OUTDOOR:
            return self.device.outdoor_temperature

    async def async_update(self):
        """Get the latest state of the sensor."""
        await self._data.update()
