"""Support for Steamist sensors."""
from __future__ import annotations

from aiosteamist import SteamistStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)


class SteamistEntity(CoordinatorEntity, Entity):
    """Representation of an Steamist entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def _status(self) -> SteamistStatus:
        """Return the steamist status."""
        return self.coordinator.data
