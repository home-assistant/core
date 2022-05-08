"""An abstract class common to all Hyyp entities."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import HyypDataUpdateCoordinator


class HyypSiteEntity(CoordinatorEntity[HyypDataUpdateCoordinator], Entity):
    """Generic entity encapsulating common features of IDS Hyyp site/device."""

    def __init__(
        self,
        coordinator: HyypDataUpdateCoordinator,
        site_id: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._site_id = site_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._site_id))},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self.data["name"],
        )

    @property
    def data(self) -> Any:
        """Return coordinator data for this entity."""
        return self.coordinator.data[self._site_id]


class HyypPartitionEntity(HyypSiteEntity):
    """Generic entity encapsulating common features of IDS Hyyp partition."""

    def __init__(
        self,
        coordinator: HyypDataUpdateCoordinator,
        site_id: int,
        partition_id: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, site_id)
        self._partition_id = partition_id

    @property
    def partition_data(self) -> Any:
        """Return partition coordinator data for this entity."""
        return self.coordinator.data[self._site_id]["partitions"][self._partition_id]
