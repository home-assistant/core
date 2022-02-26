"""Support for Honeywell (US) Total Connect Comfort sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, HUMIDITY_STATUS_KEY, TEMPERATURE_STATUS_KEY

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=TEMPERATURE_STATUS_KEY,
        name="Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=HUMIDITY_STATUS_KEY,
        name="Humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(hass, config, async_add_entities, discovery_info=None):
    """Set up the Honeywell thermostat."""
    data = hass.data[DOMAIN][config.entry_id]
    sensors = []

    for device in data.devices.values():
        for description in SENSOR_TYPES:
            if getattr(device, description.key) is not None:
                sensors.append(HoneywellSensor(device, description))

    async_add_entities(sensors)


class HoneywellSensor(SensorEntity):
    """Representation of a Honeywell US Outdoor Temperature Sensor."""

    def __init__(self, device, description):
        """Initialize the outdoor temperature sensor."""
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.deviceid}_outdoor_{description.device_class}"
        self._attr_name = f"{device.name} outdoor {description.device_class}"

        if description.key == TEMPERATURE_STATUS_KEY:
            self._attr_native_unit_of_measurement = (
                TEMP_CELSIUS
                if self._device.temperature_unit == "C"
                else TEMP_FAHRENHEIT
            )
        elif description.key == HUMIDITY_STATUS_KEY:
            self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        if self.entity_description.key == TEMPERATURE_STATUS_KEY:
            return self._device.outdoor_temperature
        if self.entity_description.key == HUMIDITY_STATUS_KEY:
            return self._device.outdoor_humidity
        return None
