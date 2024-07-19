"""Global representation of an anglian_water entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import AnglianWaterDataUpdateCoordinator


class AnglianWaterEntity(CoordinatorEntity[AnglianWaterDataUpdateCoordinator]):
    """AnglianWaterEntity class."""

    def __init__(
        self, coordinator: AnglianWaterDataUpdateCoordinator, key: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=NAME,
            manufacturer=NAME,
        )
