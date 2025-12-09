"""Base entity for Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LeilSaunaCoordinator


class LeilSaunaEntity(CoordinatorEntity[LeilSaunaCoordinator]):
    """Base entity for Saunum Leil Sauna."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LeilSaunaCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Saunum Leil",
            manufacturer="Saunum",
            model="Leil Touch Panel",
        )
