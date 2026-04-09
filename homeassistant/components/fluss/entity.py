"""Base entities for the Fluss+ integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ICON_TYPE, DEFAULT_ICON_TYPE, ICON_TYPE_MAP
from .coordinator import FlussDataUpdateCoordinator


class FlussEntity(CoordinatorEntity[FlussDataUpdateCoordinator]):
    """Base class for Fluss entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FlussDataUpdateCoordinator,
        device_id: str,
        device: dict,
    ) -> None:
        """Initialize the entity with a device ID and device data."""
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={("fluss", device_id)},
            name=device.get("deviceName"),
            manufacturer="Fluss",
            model="Fluss+ Device",
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.device_id in self.coordinator.data

    @property
    def device(self) -> dict:
        """Return the stored device data."""
        return self.coordinator.data[self.device_id]

    @property
    def _icon_type(self) -> str:
        """Return the configured icon type."""
        options = self.coordinator.config_entry.options
        return options.get(CONF_ICON_TYPE, DEFAULT_ICON_TYPE)

    @property
    def _base_icon(self) -> str:
        """Return the base (closed) mdi icon string for the configured icon type."""
        return ICON_TYPE_MAP.get(self._icon_type, "mdi:garage")
