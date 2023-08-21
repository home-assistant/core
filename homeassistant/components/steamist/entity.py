"""Support for Steamist sensors."""
from __future__ import annotations

from aiosteamist import SteamistStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SteamistDataUpdateCoordinator


class SteamistEntity(CoordinatorEntity[SteamistDataUpdateCoordinator], Entity):
    """Representation of an Steamist entity."""

    def __init__(
        self,
        coordinator: SteamistDataUpdateCoordinator,
        entry: ConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        if coordinator.device_name:
            self._attr_name = f"{coordinator.device_name} {description.name}"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        if entry.unique_id:  # Only present if UDP broadcast works
            self._attr_device_info = DeviceInfo(
                connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)},
                name=entry.data[CONF_NAME],
                manufacturer="Steamist",
                model=entry.data[CONF_MODEL],
                configuration_url=f"http://{entry.data[CONF_HOST]}",
            )

    @property
    def _status(self) -> SteamistStatus:
        """Return the steamist status."""
        return self.coordinator.data
