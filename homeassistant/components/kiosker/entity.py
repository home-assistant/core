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

        status = coordinator.data.status
        device_id = status.device_id
        model = status.model
        app_name = status.app_name
        app_version = status.app_version
        os_version = status.os_version

        # Use uppercased truncated device ID for display purposes (device name, titles)
        if device_id is not None:
            try:
                device_id_short_display = device_id[:8].upper()
            except TypeError, AttributeError:
                device_id_short_display = "unknown"
        else:
            device_id_short_display = "unknown"

        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=(f"Kiosker {device_id_short_display}"),
            manufacturer="Top North",
            model=app_name,
            sw_version=app_version,
            hw_version=(
                None
                if model is None
                else model
                if os_version is None
                else f"{model} ({os_version})"
            ),
            serial_number=device_id,
        )

        self._attr_unique_id = (
            f"{device_id}_{description.key}" if description else f"{device_id}"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data is not None
