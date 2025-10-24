"""Base entity for Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LeilSaunaCoordinator


def get_device_info(entry_id: str) -> DeviceInfo:
    """Get device info for Saunum Leil Sauna Control Unit."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Saunum Leil",
        manufacturer="Saunum",
        model="Leil Touch Panel",
    )


class LeilSaunaEntity(CoordinatorEntity[LeilSaunaCoordinator]):
    """Base entity for Saunum Leil Sauna."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LeilSaunaCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = get_device_info(coordinator.config_entry.entry_id)
