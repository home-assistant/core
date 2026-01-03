"""Base entity for NRGkick integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NRGkickData, NRGkickDataUpdateCoordinator


class NRGkickEntity(CoordinatorEntity[NRGkickDataUpdateCoordinator]):
    """Base class for NRGkick entities with common device info setup."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NRGkickDataUpdateCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._key = key
        self._setup_device_info()

    def _setup_device_info(self) -> None:
        """Set up device info and unique ID."""
        data: NRGkickData | None = self.coordinator.data
        info_data: dict[str, Any] = data.info if data else {}
        device_info: dict[str, Any] = info_data.get("general", {})

        # The config flow requires a serial number and sets it as unique_id.
        # Prefer the configured unique_id to avoid depending on runtime API data.
        serial: str = (
            self.coordinator.config_entry.unique_id
            or self.coordinator.config_entry.entry_id
        )

        versions: dict[str, Any] = info_data.get("versions", {})
        self._attr_unique_id = f"{serial}_{self._key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            serial_number=serial,
            # The config entry title already contains the device name (set in the
            # config flow), so we can reuse it here.
            name=self.coordinator.config_entry.title,
            manufacturer="DiniTech",
            model=device_info.get("model_type", "NRGkick Gen2"),
            sw_version=versions.get("sw_sm"),
        )
