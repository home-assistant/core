"""Base entity for the BACnet integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .bacnet_client import BACnetObjectInfo
from .const import CONF_HUB_ID, DOMAIN
from .coordinator import BACnetDeviceCoordinator


class BACnetEntity(CoordinatorEntity[BACnetDeviceCoordinator]):
    """Base class for BACnet entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BACnetDeviceCoordinator,
        object_info: BACnetObjectInfo,
    ) -> None:
        """Initialize the BACnet entity."""
        super().__init__(coordinator)

        self._object_info = object_info
        self._obj_key = f"{object_info.object_type},{object_info.object_instance}"

        device_info = coordinator.device_info
        self._attr_unique_id = (
            f"{device_info.device_id}-{object_info.object_type}"
            f"-{object_info.object_instance}"
        )

        # Set entity name from BACnet object name
        if object_info.object_name:
            self._attr_name = object_info.object_name
        else:
            self._attr_name = f"{object_info.object_type} {object_info.object_instance}"

        # Build device info
        via_device: tuple[str, str] | None = None
        hub_entry_id = coordinator.config_entry.data.get(CONF_HUB_ID)
        if hub_entry_id:
            hub_entry = coordinator.hass.config_entries.async_get_entry(hub_entry_id)
            if hub_entry and hub_entry.runtime_data:
                via_device = (DOMAIN, hub_entry.runtime_data.hub_device_id)

        connections: set[tuple[str, str]] | None = None
        if device_info.mac_address:
            connections = {(CONNECTION_NETWORK_MAC, device_info.mac_address)}

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_info.device_id))},
            name=device_info.name or f"BACnet device {device_info.device_id}",
            manufacturer=device_info.vendor_name or "BACnet",
            model=device_info.model_name,
            serial_number=f"{device_info.device_id} @ {device_info.address}",
            sw_version=device_info.firmware_revision,
            hw_version=device_info.hardware_version,
        )
        if via_device is not None:
            self._attr_device_info["via_device"] = via_device
        if connections is not None:
            self._attr_device_info["connections"] = connections

    @property
    def _current_value(self) -> object:
        """Get the current value from coordinator data."""
        if self.coordinator.data is not None:
            return self.coordinator.data.values.get(self._obj_key)
        return None
