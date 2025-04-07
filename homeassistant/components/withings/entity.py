"""Base entity for Withings."""

from __future__ import annotations

from typing import Any

from aiowithings import Device

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    WithingsDataUpdateCoordinator,
    WithingsDeviceDataUpdateCoordinator,
)


class WithingsEntity[_T: WithingsDataUpdateCoordinator[Any]](CoordinatorEntity[_T]):
    """Base class for withings entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: _T,
        key: str,
    ) -> None:
        """Initialize the Withings entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"withings_{coordinator.config_entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.config_entry.unique_id))},
            manufacturer="Withings",
        )


class WithingsDeviceEntity(WithingsEntity[WithingsDeviceDataUpdateCoordinator]):
    """Base class for withings device entities."""

    def __init__(
        self,
        coordinator: WithingsDeviceDataUpdateCoordinator,
        device_id: str,
        key: str,
    ) -> None:
        """Initialize the Withings entity."""
        super().__init__(coordinator, key)
        self._attr_unique_id = f"{device_id}_{key}"
        self.device_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Withings",
            name=self.device.raw_model,
            model=self.device.raw_model,
            via_device=(DOMAIN, str(coordinator.config_entry.unique_id)),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.device_id in self.coordinator.data

    @property
    def device(self) -> Device:
        """Return the Withings device."""
        return self.coordinator.data[self.device_id]
