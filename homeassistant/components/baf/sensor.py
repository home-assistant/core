"""Support for Big Ass Fans sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from aiobafi6 import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BAFConfigEntry
from .entity import BAFDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class BAFSensorDescription(
    SensorEntityDescription,
):
    """Class describing BAF sensor entities."""

    value_fn: Callable[[Device], int | float | str | None]


AUTO_COMFORT_SENSORS = (
    BAFSensorDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: cast(float | None, device.temperature),
    ),
)

DEFINED_ONLY_SENSORS = (
    BAFSensorDescription(
        key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: cast(float | None, device.humidity),
    ),
)

FAN_SENSORS = (
    BAFSensorDescription(
        key="current_rpm",
        translation_key="current_rpm",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: cast(int | None, device.current_rpm),
    ),
    BAFSensorDescription(
        key="target_rpm",
        translation_key="target_rpm",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: cast(int | None, device.target_rpm),
    ),
    BAFSensorDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: cast(int | None, device.wifi_ssid),
    ),
    BAFSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: cast(str | None, device.ip_address),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BAFConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BAF fan sensors."""
    device = entry.runtime_data
    sensors_descriptions: list[BAFSensorDescription] = [
        description
        for description in DEFINED_ONLY_SENSORS
        if getattr(device, description.key)
    ]
    if device.has_auto_comfort:
        sensors_descriptions.extend(AUTO_COMFORT_SENSORS)
    if device.has_fan:
        sensors_descriptions.extend(FAN_SENSORS)
    async_add_entities(
        BAFSensor(device, description) for description in sensors_descriptions
    )


class BAFSensor(BAFDescriptionEntity, SensorEntity):
    """BAF sensor."""

    entity_description: BAFSensorDescription

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_native_value = self.entity_description.value_fn(self._device)
