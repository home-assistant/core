"""Sensors for PTDevices device."""

from __future__ import annotations

import logging
from string import ascii_letters
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PTDevicesCoordinator

_LOGGER = logging.getLogger(__name__)

RESOURCES: dict[str, SensorEntityDescription] = {
    "percent_level": SensorEntityDescription(
        key="percent_level",
        translation_key="level_percent",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "volume_level": SensorEntityDescription(
        key="volume_level",
        translation_key="level_volume",
        device_class=SensorDeviceClass.WATER,
    ),
    "inch_level": SensorEntityDescription(
        key="inch_level",
        translation_key="level_depth",
        native_unit_of_measurement=UnitOfLength.INCHES,
    ),
    "probe_temperature": SensorEntityDescription(
        key="probe_temperature",
        translation_key="temperature_probe",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "title": SensorEntityDescription(
        key="title",
        translation_key="device_title",
        entity_registry_enabled_default=False,
    ),
    "id": SensorEntityDescription(
        key="id",
        translation_key="device_id",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "device_id": SensorEntityDescription(
        key="device_id",
        translation_key="device_mac",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "share_id": SensorEntityDescription(
        key="share_id",
        translation_key="device_share_id",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "created": SensorEntityDescription(
        key="created",
        translation_key="device_created",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "user_id": SensorEntityDescription(
        key="user_id",
        translation_key="user_id",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "device_type": SensorEntityDescription(
        key="device_type",
        translation_key="device_type",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "version": SensorEntityDescription(
        key="version",
        translation_key="device_version",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "address": SensorEntityDescription(
        key="address",
        translation_key="device_addr",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "status": SensorEntityDescription(
        key="status",
        translation_key="device_status",
    ),
    "delivery_notes": SensorEntityDescription(
        key="delivery_notes",
        translation_key="device_delivery_notes",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "units": SensorEntityDescription(
        key="units",
        translation_key="device_units",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "reported": SensorEntityDescription(
        key="reported",
        translation_key="device_reported",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "tx_reported": SensorEntityDescription(
        key="tx_reported",
        translation_key="tx_reported",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "last_updated_on": SensorEntityDescription(
        key="last_updated_on",
        translation_key="rx_updated_on",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "wifi_signal": SensorEntityDescription(
        key="wifi_signal",
        translation_key="device_wifi_signal",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "tx_signal": SensorEntityDescription(
        key="tx_signal",
        translation_key="tx_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}

SENSORS_UNITS: dict[str, SensorEntityDescription] = {}


def _format_dict(input: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    # Recurse through key value pairs and convert from nested to flat
    def recurse(sub_dict: dict[str, Any]):
        for key, value in sub_dict.items():
            if isinstance(value, dict):
                recurse(value)

            else:
                if key not in RESOURCES:
                    continue

                result[key] = value

    recurse(input)

    return result


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PTDevices sensors from config entries."""
    coordinator: PTDevicesCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    await coordinator.async_refresh()

    if coordinator.data is None or coordinator.data["body"] is None:
        _LOGGER.error("No data available")
        return

    # Get the dict and flatten it
    body: dict[str, Any] = _format_dict(coordinator.data["body"])

    # Collect all available resources
    entities = [PTDevicesSensor(coordinator, RESOURCES[resource]) for resource in body]

    async_add_entities(entities)


class PTDevicesSensor(SensorEntity, CoordinatorEntity[PTDevicesCoordinator]):
    """Sensor entity for PTDevices Integration."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: PTDevicesCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator=coordinator, context=description.key.upper())

        # Get the mac address for use in the device id
        mac: str = self.coordinator.data.get("body", {}).get("device_id", "")

        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{mac}_{description.key}"

        # Initial Update
        self._update_attrs()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.entity_description.key in _format_dict(
            self.coordinator.data.get("body", {})
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()

    def _update_attrs(self) -> None:
        """Update sensor attributes based on coordinator data."""
        data = _format_dict(self.coordinator.data.get("body", {}))
        key = self.entity_description.key

        # If the key was not found, set the entity to unavailable and exit, else, continue
        if key not in data:
            self._attr_available = False
            return

        self._attr_available = True

        value = data.get(key)

        if self.device_class is SensorDeviceClass.WATER:
            if data.get("units") == "Metric":
                self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
            elif (
                data.get("units") == "British Imperial"
                or data.get("units") == "US Imperial"
            ):
                self._attr_native_unit_of_measurement = UnitOfVolume.GALLONS

        if self.native_unit_of_measurement is not None and isinstance(value, str):
            self._attr_native_value = float(value.strip(ascii_letters + "%"))
        else:
            self._attr_native_value = value
