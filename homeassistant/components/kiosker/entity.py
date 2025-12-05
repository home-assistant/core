"""Base entity for Kiosker."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KioskerDataUpdateCoordinator


class KioskerEntity(CoordinatorEntity[KioskerDataUpdateCoordinator]):
    """Base class for Kiosker entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KioskerDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        # Get device info with fallbacks for translation detection
        device_id = self._get_device_id()
        model = self._get_model()
        hw_version = self._get_hw_version()
        sw_version = self._get_sw_version()
        app_name = self._get_app_name()

        # Ensure device info is always created, even without coordinator data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=f"Kiosker {device_id[:8]}" if device_id != "unknown" else "Kiosker",
            manufacturer="Top North",
            model=app_name,
            sw_version=sw_version,
            hw_version=f"{model} ({hw_version})",
            serial_number=device_id,
        )

    def _get_status_attribute(self, attribute: str, default: str = "Unknown") -> str:
        """Get attribute from coordinator status data."""
        if (
            self.coordinator.data
            and "status" in self.coordinator.data
            and hasattr(self.coordinator.data["status"], attribute)
        ):
            return getattr(self.coordinator.data["status"], attribute)
        return default

    def _get_device_id(self) -> str:
        """Get device ID from coordinator data."""
        return self._get_status_attribute("device_id", "unknown")

    def _get_app_name(self) -> str:
        """Get app name from coordinator data."""
        return self._get_status_attribute("app_name")

    def _get_model(self) -> str:
        """Get model from coordinator data."""
        return self._get_status_attribute("model")

    def _get_sw_version(self) -> str:
        """Get software version from coordinator data."""
        return self._get_status_attribute("app_version")

    def _get_hw_version(self) -> str:
        """Get hardware version from coordinator data."""
        return self._get_status_attribute("os_version")
