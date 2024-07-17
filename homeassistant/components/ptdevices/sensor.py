"""Sensors for PTDevices device."""

from __future__ import annotations

import logging
from string import ascii_letters
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfLength,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PTDevicesCoordinator

_LOGGER = logging.getLogger(__name__)

RESOURCES: dict[str, SensorEntityDescription] = {
    "id": SensorEntityDescription(
        key="id",
        translation_key="device_id",
    ),
    "device_id": SensorEntityDescription(
        key="device_id",
        translation_key="device_mac",
    ),
    "share_id": SensorEntityDescription(
        key="share_id",
        translation_key="device_share_id",
        entity_registry_enabled_default=True,
    ),
    "created": SensorEntityDescription(
        key="created",
        translation_key="device_created",
        entity_registry_enabled_default=False,
    ),
    "user_id": SensorEntityDescription(
        key="user_id",
        translation_key="user_id",
    ),
    "device_type": SensorEntityDescription(
        key="device_type",
        translation_key="device_type",
    ),
    "title": SensorEntityDescription(
        key="title",
        translation_key="device_title",
    ),
    "version": SensorEntityDescription(
        key="version",
        translation_key="device_version",
    ),
    "address": SensorEntityDescription(
        key="address",
        translation_key="device_addr",
    ),
    "status": SensorEntityDescription(
        key="status",
        translation_key="device_status",
    ),
    "delivery_notes": SensorEntityDescription(
        key="delivery_notes",
        translation_key="device_delivery_notes",
    ),
    "units": SensorEntityDescription(
        key="units",
        translation_key="device_units",
    ),
    "reported": SensorEntityDescription(
        key="reported",
        translation_key="device_reported",
        entity_registry_enabled_default=False,
    ),
    "tx_reported": SensorEntityDescription(
        key="tx_reported",
        translation_key="tx_reported",
        entity_registry_enabled_default=False,
    ),
    "last_updated_on": SensorEntityDescription(
        key="last_updated_on",
        translation_key="rx_updated_on",
        entity_registry_enabled_default=False,
    ),
    "wifi_signal": SensorEntityDescription(
        key="wifi_signal",
        translation_key="device_wifi_signal",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "tx_signal": SensorEntityDescription(
        key="tx_signal",
        translation_key="tx_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ),
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
    async_add_entities: AddEntitiesCallback,
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


class PTDevicesSensor(CoordinatorEntity[PTDevicesCoordinator], SensorEntity):
    """Sensor entity for PTDevices Integration."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: PTDevicesCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator=coordinator, context=description.key.upper())

        # Get the mac address for use in the device id
        mac: str = self.coordinator.data["body"]["device_id"]

        self._attr_unique_id = f"{mac}_{description.key}"

        self.entity_description = description
        self._attr_device_info = coordinator.device_info

        # Initial Update
        self._update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()

    def _update_attrs(self) -> None:
        """Update sensor attributes based on coordinator data."""
        data = _format_dict(self.coordinator.data["body"])
        key = self.entity_description.key

        if self.device_class is SensorDeviceClass.WATER:
            if data["units"] == "Metric":
                self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
            elif data["units"] == "British Imperial" or data["units"] == "US Imperial":
                self._attr_native_unit_of_measurement = UnitOfVolume.GALLONS

        if self.native_unit_of_measurement is not None and isinstance(data[key], str):
            self._attr_native_value = float(data[key].strip(ascii_letters + "%"))
        else:
            self._attr_native_value = data[key]
