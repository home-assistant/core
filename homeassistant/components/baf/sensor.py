"""Support for Big Ass Fans sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional, cast

from aiobafi6 import Device

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, REVOLUTIONS_PER_MINUTE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BAFEntity
from .models import BAFData


@dataclass
class BAFSensorDescriptionMixin:
    """Required values for BAF sensors."""

    value_fn: Callable[[Device], int | float | str | None]


@dataclass
class BAFSensorDescription(
    SensorEntityDescription,
    BAFSensorDescriptionMixin,
):
    """Class describing BAF sensor entities."""


AUTO_COMFORT_SENSORS = (
    BAFSensorDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: cast(Optional[float], device.temperature),
    ),
)

DEFINED_ONLY_SENSORS = (
    BAFSensorDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: cast(Optional[float], device.humidity),
    ),
)

FAN_SENSORS = (
    BAFSensorDescription(
        key="current_rpm",
        name="Current RPM",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: cast(Optional[int], device.current_rpm),
    ),
    BAFSensorDescription(
        key="target_rpm",
        name="Target RPM",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: cast(Optional[int], device.target_rpm),
    ),
    BAFSensorDescription(
        key="wifi_ssid",
        name="WiFi SSID",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: cast(Optional[int], device.wifi_ssid),
    ),
    BAFSensorDescription(
        key="ip_address",
        name="IP Address",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: cast(Optional[str], device.ip_address),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BAF fan sensors."""
    data: BAFData = hass.data[DOMAIN][entry.entry_id]
    device = data.device
    sensors_descriptions: list[BAFSensorDescription] = []
    for description in DEFINED_ONLY_SENSORS:
        if getattr(device, description.key):
            sensors_descriptions.append(description)
    if device.has_auto_comfort:
        sensors_descriptions.extend(AUTO_COMFORT_SENSORS)
    if device.has_fan:
        sensors_descriptions.extend(FAN_SENSORS)
    async_add_entities(
        BAFSensor(device, description) for description in sensors_descriptions
    )


class BAFSensor(BAFEntity, SensorEntity):
    """BAF sensor."""

    entity_description: BAFSensorDescription

    def __init__(self, device: Device, description: BAFSensorDescription) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(device, f"{device.name} {description.name}")
        self._attr_unique_id = f"{self._device.mac_address}-{description.key}"

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        description = self.entity_description
        self._attr_native_value = description.value_fn(self._device)
