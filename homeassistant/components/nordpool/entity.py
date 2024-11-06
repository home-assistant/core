"""Base entity for Nord Pool."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NordpooolDataUpdateCoordinator


class NordpoolBaseEntity(CoordinatorEntity[NordpooolDataUpdateCoordinator]):
    """Representation of a Nord Pool base entity."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NordpooolDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
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
