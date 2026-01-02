"""Base entity for MELCloud integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MelCloudDevice, MelCloudDeviceUpdateCoordinator


class MelCloudEntity(CoordinatorEntity[MelCloudDeviceUpdateCoordinator]):
    """Base class for MELCloud entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api: MelCloudDevice,
    ) -> None:
        """Initialize the entity."""
        super().__init__(api.coordinator)
        self._api = api

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._api.available
