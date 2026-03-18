"""Base entity for Qube Heat Pump."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import QubeConfigEntry
from .const import DOMAIN
from .coordinator import QubeCoordinator


class QubeEntity(CoordinatorEntity[QubeCoordinator]):
    """Base entity for Qube Heat Pump."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: QubeCoordinator,
        entry: QubeConfigEntry,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        assert entry.unique_id is not None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title,
            manufacturer="Qube",
            model="Heat Pump",
            sw_version=entry.runtime_data.sw_version,
        )
