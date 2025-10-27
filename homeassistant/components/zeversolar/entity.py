"""Base Entity for Zeversolar sensors."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZeversolarCoordinator


class ZeversolarEntity(
    CoordinatorEntity[ZeversolarCoordinator],
):
    """Defines a base Zeversolar entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: ZeversolarCoordinator,
    ) -> None:
        """Initialize the Zeversolar entity."""
        super().__init__(coordinator=coordinator)
        # Use current data or last known data for device info
        device_data = coordinator.data or coordinator.last_known_data
        host = coordinator.config_entry.data.get("host", "unknown")

        if device_data:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device_data.serial_number)},
                name="Zeversolar Inverter",
                manufacturer="Zeversolar",
                serial_number=device_data.serial_number,
                suggested_area="Solar System",
            )
        else:
            # Use host-based device info when no data is available (offline setup)
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"zeversolar_{host}")},
                name="Zeversolar Inverter",
                manufacturer="Zeversolar",
                suggested_area="Solar System",
            )
