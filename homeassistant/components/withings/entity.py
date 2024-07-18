"""Base entity for Withings."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WithingsDataUpdateCoordinator


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
