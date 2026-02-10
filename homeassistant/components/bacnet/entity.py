"""Base entity for the BACnet integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .bacnet_client import BACnetObjectInfo
from .const import DOMAIN
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

        # Build device info for this BACnet device
        connections: set[tuple[str, str]] | None = None
        if device_info.mac_address:
            connections = {(CONNECTION_NETWORK_MAC, device_info.mac_address)}

        # Show IP address alongside model in the integration device list
        address_display = device_info.address.split(":")[0]
        if device_info.model_name:
            model = f"{device_info.model_name} ({address_display})"
        else:
            model = address_display

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_info.device_id))},
            name=device_info.name or f"BACnet device {device_info.device_id}",
            manufacturer=device_info.vendor_name or "BACnet",
            model=model,
            serial_number=f"{device_info.device_id} @ {device_info.address}",
            sw_version=device_info.firmware_revision,
            hw_version=device_info.hardware_version,
        )
        if connections is not None:
            self._attr_device_info["connections"] = connections

    @property
    def _current_object_info(self) -> BACnetObjectInfo | None:
        """Get the current object info from coordinator data."""
        if self.coordinator.data is None:
            return None
        for obj in self.coordinator.data.objects:
            if f"{obj.object_type},{obj.object_instance}" == self._obj_key:
                return obj
        return None

    @property
    def _current_value(self) -> object:
        """Get the current value from coordinator data."""
        if self.coordinator.data is not None:
            return self.coordinator.data.values.get(self._obj_key)
        return None
