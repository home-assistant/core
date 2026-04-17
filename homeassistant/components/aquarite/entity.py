"""Shared base entity helpers for Aquarite."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRAND, DOMAIN, MODEL
from .coordinator import AquariteDataUpdateCoordinator


class AquariteEntity(CoordinatorEntity[AquariteDataUpdateCoordinator]):
    """Base entity class for Aquarite platforms (one device per pool)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AquariteDataUpdateCoordinator) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        sw_version = coordinator.get_value("main.version")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.pool_id)},
            name=coordinator.pool_name,
            manufacturer=BRAND,
            model=MODEL,
            sw_version=str(sw_version) if sw_version is not None else None,
        )

    @property
    def pool_id(self) -> str:
        """Return the pool ID for the entity."""
        return self.coordinator.pool_id

    @property
    def pool_name(self) -> str:
        """Return the friendly pool name for the entity."""
        return self.coordinator.pool_name

    def build_unique_id(self, suffix: str) -> str:
        """Return a consistent unique ID for the entity."""
        return f"{self.coordinator.pool_id}-{suffix}"
