"""Support for DayBetter sensors."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up DayBetter sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    devices = data["devices"]

    # Ensure devices is a list, even if it's None
    if devices is None:
        devices = []

    _LOGGER.debug("Setting up sensors for %d devices", len(devices))

    entities: list[SensorEntity] = []
    for device in devices:
        device_type = device.get("type", 0)

        # Only create sensors for device type 5 (temperature/humidity sensors)
        if device_type == 5:
            # Create temperature sensor if temperature data exists
            if "temperature" in device:
                entities.append(DayBetterTemperatureSensor(device))

            # Create humidity sensor if humidity data exists
            if "humidity" in device:
                entities.append(DayBetterHumiditySensor(device))

    async_add_entities(entities, True)


class DayBetterTemperatureSensor(SensorEntity):
    """Representation of a DayBetter temperature sensor."""

    def __init__(self, device: dict[str, Any]) -> None:
        """Initialize the temperature sensor."""
        self._device = device
        self._device_name = device.get("deviceName", "unknown")
        self._device_group_name = device.get("deviceGroupName", "DayBetter Sensor")

        # Set sensor attributes
        self._attr_name = f"{self._device_group_name} Temperature"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

        # Initialize temperature value
        self._attr_native_value = device.get("temperature", 20.0)

        # Generate unique ID
        device_id = device.get("id", "")
        self._attr_unique_id = f"daybetter_temp_{self._device_name}_{device_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_name)},
            name=self._device_group_name,
            manufacturer="DayBetter",
            model="Temperature Sensor",
        )


class DayBetterHumiditySensor(SensorEntity):
    """Representation of a DayBetter humidity sensor."""

    def __init__(self, device: dict[str, Any]) -> None:
        """Initialize the humidity sensor."""
        self._device = device
        self._device_name = device.get("deviceName", "unknown")
        self._device_group_name = device.get("deviceGroupName", "DayBetter Sensor")

        # Set sensor attributes
        self._attr_name = f"{self._device_group_name} Humidity"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.HUMIDITY
        self._attr_state_class = SensorStateClass.MEASUREMENT

        # Initialize humidity value
        self._attr_native_value = device.get("humidity", 50.0)

        # Generate unique ID
        device_id = device.get("id", "")
        self._attr_unique_id = f"daybetter_humidity_{self._device_name}_{device_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_name)},
            name=self._device_group_name,
            manufacturer="DayBetter",
            model="Humidity Sensor",
        )
