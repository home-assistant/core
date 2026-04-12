"""Shared base entity helpers for Aquarite."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRAND, DOMAIN, MODEL
from .coordinator import AquariteDataUpdateCoordinator


class AquariteEntity(CoordinatorEntity[AquariteDataUpdateCoordinator]):
    """Base entity class for Aquarite platforms."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._pool_id = pool_id
        self._pool_name = pool_name
        sw_version = coordinator.get_value("main.version")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pool_id)},
            name=pool_name,
            manufacturer=BRAND,
            model=MODEL,
            sw_version=str(sw_version) if sw_version else None,
        )

    @property
    def pool_id(self) -> str:
        """Return the pool ID for the entity."""
        return self._pool_id

    @property
    def pool_name(self) -> str:
        """Return the friendly pool name for the entity."""
        return self._pool_name

    def build_unique_id(self, suffix: str) -> str:
        """Return a consistent unique ID for the entity."""
        return f"{self._pool_id}-{suffix}"
