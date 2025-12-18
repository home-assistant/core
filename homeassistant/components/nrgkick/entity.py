"""Base entity for NRGkick integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NRGkickDataUpdateCoordinator


class NRGkickEntity(CoordinatorEntity[NRGkickDataUpdateCoordinator]):
    """Base class for NRGkick entities with common device info setup."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NRGkickDataUpdateCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = key
        self._setup_device_info()

    @property
    def suggested_object_id(self) -> str | None:
        """Return the suggested object ID for this entity.

        This ensures entity_ids are always English-based (e.g.,
        sensor.nrgkick_total_active_power) regardless of the user's
        language setting, while still allowing translated display names
        in the UI via translation_key.

        """
        return self._key

    def _setup_device_info(self) -> None:
        """Set up device info and unique ID."""
        data = self.coordinator.data
        info_data: dict[str, Any] = data.get("info", {}) if data else {}
        device_info: dict[str, Any] = info_data.get("general", {})
        serial: str = device_info.get("serial_number", "unknown")

        device_name: str | None = device_info.get("device_name")
        if not device_name:
            device_name = "NRGkick"

        versions: dict[str, Any] = info_data.get("versions", {})
        self._attr_unique_id = f"{serial}_{self._key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=device_name,
            manufacturer="DiniTech",
            model=device_info.get("model_type", "NRGkick Gen2"),
            sw_version=versions.get("sw_sm"),
        )
