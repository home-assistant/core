"""Support for Steamist sensors."""

from aiosteamist import MODEL_550, SteamistStatus

from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SteamistConfigEntry, SteamistDataUpdateCoordinator


class SteamistEntity(CoordinatorEntity[SteamistDataUpdateCoordinator], Entity):
    """Representation of a Steamist entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SteamistDataUpdateCoordinator,
        entry: SteamistConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        if entry.unique_id:  # Only present if UDP broadcast works
            model = entry.data.get(CONF_MODEL)
            configuration_url = (
                None if model == MODEL_550 else f"http://{entry.data[CONF_HOST]}"
            )
            self._attr_device_info = DeviceInfo(
                connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)},
                manufacturer="Steamist",
                model=model,
                configuration_url=configuration_url,
            )

    @property
    def _status(self) -> SteamistStatus:
        """Return the steamist status."""
        return self.coordinator.data
