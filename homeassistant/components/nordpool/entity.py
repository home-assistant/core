"""Base entity for Nord Pool."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NordPoolDataUpdateCoordinator


class NordpoolBaseEntity(CoordinatorEntity[NordPoolDataUpdateCoordinator]):
    """Representation of a Nord Pool base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NordPoolDataUpdateCoordinator,
        entity_description: EntityDescription,
        area: str,
    ) -> None:
        """Initiate Nord Pool base entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{area}-{entity_description.key}"
        self.area = area
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, area)},
            name=f"Nord Pool {area}",
        )
