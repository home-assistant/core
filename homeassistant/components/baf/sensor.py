"""Support for Big Ass Fans sensors."""
from __future__ import annotations

from aiobafi6 import Device

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BAFEntity
from .models import BAFData

BASE_SENSORS = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

DEFINED_ONLY_SENSORS = (
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

FAN_SENSORS = (
    SensorEntityDescription(
        key="current_rpm",
        name="Current RPM",
        native_unit_of_measurement="RPM",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="target_rpm",
        name="Target RPM",
        native_unit_of_measurement="RPM",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="wifi_ssid", name="WiFi SSID", entity_registry_enabled_default=False
    ),
    SensorEntityDescription(
        key="ip_address", name="IP Address", entity_registry_enabled_default=False
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
    sensors_descriptions = list(BASE_SENSORS)
    for description in DEFINED_ONLY_SENSORS:
        if getattr(device, description.key):
            sensors_descriptions.append(description)
    if device.has_fan:
        sensors_descriptions.extend(FAN_SENSORS)
    async_add_entities(
        BAFSensor(device, description) for description in sensors_descriptions
    )


class BAFSensor(BAFEntity, SensorEntity):
    """BAF sensor."""

    entity_description: SensorEntityDescription

    def __init__(self, device: Device, description: SensorEntityDescription) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(device, f"{device.name} {description.name}")
        self._attr_unique_id = f"{self._device.mac_address}-{description.key}"

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_native_value = getattr(self._device, self.entity_description.key)
