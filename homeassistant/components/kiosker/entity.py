"""Base entity for Kiosker."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KioskerDataUpdateCoordinator


class KioskerEntity(CoordinatorEntity[KioskerDataUpdateCoordinator]):
    """Base class for Kiosker entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KioskerDataUpdateCoordinator,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        if description:
            self.entity_description = description

        # Use coordinator data if available, otherwise fallback to config entry data
        if coordinator.data and coordinator.data.status:
            status = coordinator.data.status
            device_id = status.device_id
            model = status.model
            app_name = status.app_name
            app_version = status.app_version
            os_version = status.os_version
        else:
            # Fallback when no data is available yet
            device_id = None
            model = None
            app_name = None
            app_version = None
            os_version = None

        # Use uppercased truncated device ID for display purposes (device name, titles)
        device_id_short_display = (
            device_id[:8].upper() if device_id != "unknown" else None
        )

        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=(
                f"Kiosker {device_id_short_display}"
                if device_id is not None
                else "Kiosker"
            ),
            manufacturer="Top North",
            model=app_name,
            sw_version=app_version,
            hw_version=f"{model} ({os_version})",
            serial_number=device_id,
        )

        self._attr_unique_id = (
            f"{device_id}_{description.key}" if description else f"{device_id}"
        )
