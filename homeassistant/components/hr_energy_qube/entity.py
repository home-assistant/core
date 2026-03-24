"""Base entity for Qube Heat Pump."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import QubeCoordinator

if TYPE_CHECKING:
    from . import QubeConfigEntry


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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Qube",
            model="Heat Pump",
            sw_version=entry.runtime_data.sw_version,
        )
