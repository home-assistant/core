"""Base Entity for Roku."""
from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RokuDataUpdateCoordinator
from .const import DOMAIN


class RokuEntity(CoordinatorEntity[RokuDataUpdateCoordinator]):
    """Defines a base Roku entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        device_id: str,
        coordinator: RokuDataUpdateCoordinator,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the Roku entity."""
        super().__init__(coordinator)
        self._device_id = device_id

        if description is not None:
            self.entity_description = description
            self._attr_unique_id = f"{device_id}_{description.key}"
        else:
            self._attr_unique_id = device_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            connections={
                (CONNECTION_NETWORK_MAC, mac_address)
                for mac_address in (
                    self.coordinator.data.info.wifi_mac,
                    self.coordinator.data.info.ethernet_mac,
                )
                if mac_address is not None
            },
            name=self.coordinator.data.info.name,
            manufacturer=self.coordinator.data.info.brand,
            model=self.coordinator.data.info.model_name,
            hw_version=self.coordinator.data.info.model_number,
            sw_version=self.coordinator.data.info.version,
            suggested_area=self.coordinator.data.info.device_location,
        )
