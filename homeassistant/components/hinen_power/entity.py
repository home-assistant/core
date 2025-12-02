"""Entity representing a Hinen."""

from __future__ import annotations

from hinen_open_api import HinenOpen

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DEVICE_NAME, DOMAIN, MANUFACTURER
from .coordinator import HinenDataUpdateCoordinator


class HinenDeviceEntity(CoordinatorEntity[HinenDataUpdateCoordinator]):
    """An HA implementation for Hinen entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HinenDataUpdateCoordinator,
        hinen_open: HinenOpen,
        description: EntityDescription,
        device_id: str,
    ) -> None:
        """Initialize a Hinen entity."""
        super().__init__(coordinator)
        self.hinen_open = hinen_open
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{device_id}_{description.key}"
        )
        self._device_id = device_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_{device_id}")},
            manufacturer=MANUFACTURER,
            name=f"{coordinator.data[device_id][ATTR_DEVICE_NAME]}",
        )
