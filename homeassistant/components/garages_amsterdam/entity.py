"""Generic entity for Garages Amsterdam."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import GaragesAmsterdamDataUpdateCoordinator


class GaragesAmsterdamEntity(CoordinatorEntity[GaragesAmsterdamDataUpdateCoordinator]):
    """Base Entity for garages amsterdam data."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GaragesAmsterdamDataUpdateCoordinator,
        garage_name: str,
    ) -> None:
        """Initialize garages amsterdam entity."""
        super().__init__(coordinator)
        self._garage_name = garage_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, garage_name)},
            name=garage_name,
            entry_type=DeviceEntryType.SERVICE,
        )
