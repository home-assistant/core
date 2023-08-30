"""Generic entity for Garages Amsterdam."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTRIBUTION, DOMAIN


class GaragesAmsterdamEntity(CoordinatorEntity):
    """Base Entity for garages amsterdam data."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DataUpdateCoordinator, garage_name: str, info_type: str
    ) -> None:
        """Initialize garages amsterdam entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{garage_name}-{info_type}"
        self._garage_name = garage_name
        self._info_type = info_type
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, garage_name)},
            name=garage_name,
            entry_type=DeviceEntryType.SERVICE,
        )
