"""Base entity for the BACnet integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
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

        # Build device info with all available fields
        device_info_dict = {
            "identifiers": {(DOMAIN, str(device_info.device_id))},
            "name": device_info.name or f"BACnet device {device_info.device_id}",
            "manufacturer": device_info.vendor_name or "BACnet",
        }

        # Link to parent hub if this device has a hub entry
        hub_entry_id = coordinator.config_entry.data.get(CONF_HUB_ID)
        if hub_entry_id:
            hub_entry = coordinator.hass.config_entries.async_get_entry(hub_entry_id)
            if hub_entry and hub_entry.runtime_data:
                device_info_dict["via_device"] = (DOMAIN, hub_entry.runtime_data.hub_device_id)

        # Add model - keep it simple
        if device_info.model_name:
            device_info_dict["model"] = device_info.model_name

        # Add serial number using device ID for identification
        device_info_dict["serial_number"] = f"{device_info.device_id} @ {device_info.address}"

        if device_info.firmware_revision:
            device_info_dict["sw_version"] = device_info.firmware_revision

        if device_info.hardware_version:
            device_info_dict["hw_version"] = device_info.hardware_version

        # Add MAC address as connection if available
        if device_info.mac_address:
            device_info_dict["connections"] = {("mac", device_info.mac_address)}

        self._attr_device_info = DeviceInfo(**device_info_dict)

    @property
    def _current_value(self) -> object:
        """Get the current value from coordinator data."""
        if self.coordinator.data is not None:
            return self.coordinator.data.values.get(self._obj_key)
        return None
