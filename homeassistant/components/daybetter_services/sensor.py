"""Support for DayBetter sensors."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up DayBetter sensors from a config entry."""
    runtime_data = entry.runtime_data
    devices = runtime_data.devices

    # Ensure devices is a list, even if it's None
    if devices is None:
        devices = []

    _LOGGER.debug("Setting up sensors for %d devices", len(devices))

    entities = []
    for device in devices:
        device_type = device.get("type", 0)
        
        # Only create sensors for device type 5 (temperature/humidity sensors)
        if device_type == 5:
            device_name = device.get("deviceName", "unknown")
            device_group_name = device.get("deviceGroupName", "DayBetter Sensor")
            
            # Create temperature sensor if temperature data exists
            if "temperature" in device:
                entities.append(
                    DayBetterSensor(
                        device=device,
                        device_name=device_name,
                        device_group_name=device_group_name,
                        entity_description=SENSOR_DESCRIPTIONS[0],
                    )
                )
            
            # Create humidity sensor if humidity data exists
            if "humidity" in device:
                entities.append(
                    DayBetterSensor(
                        device=device,
                        device_name=device_name,
                        device_group_name=device_group_name,
                        entity_description=SENSOR_DESCRIPTIONS[1],
                    )
                )

    async_add_entities(entities, True)


class DayBetterSensor(SensorEntity):
    """Representation of a DayBetter sensor."""

    def __init__(
        self,
        device: dict[str, Any],
        device_name: str,
        device_group_name: str,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self._device = device
        self._device_name = device_name
        self._device_group_name = device_group_name
        self.entity_description = entity_description

        # Set sensor attributes
        self._attr_name = f"{self._device_group_name} {entity_description.name}"
        self._attr_unique_id = f"daybetter_{entity_description.key}_{device_name}_{device.get('id', '')}"

        # Initialize sensor value
        self._attr_native_value = device.get(entity_description.key, 0.0)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_name)},
            name=self._device_group_name,
            manufacturer="DayBetter",
            model="Environmental Sensor",
        )

    async def async_update(self) -> None:
        """Update sensor data."""
        # For now, we'll use the initial data
        # In a future PR, we'll add proper data updates
        self._attr_native_value = self._device.get(self.entity_description.key, 0.0)