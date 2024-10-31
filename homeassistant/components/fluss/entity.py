"""Base entities for the Fluss+ integration."""

import logging

from fluss_api import FlussApiClientCommunicationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity, EntityDescription

_LOGGER = logging.getLogger(__name__)


class FlussEntity(Entity):
    """Base class for Fluss entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        device: object,
        entry: ConfigEntry,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        self.hass = hass
        self.device = device
        self.entry = entry
        self.entity_description = entity_description

    def _update_entry_data(self) -> None:
        """Update the entry data if necessary."""
        new_address = getattr(self.device, "unique_id", None)
        new_data = {**self.entry.data, "address": new_address}

        if new_data != self.entry.data:
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)

    async def async_update(self):
        """Fetch new state data for the entity."""
        _LOGGER.debug("Updating FlussEntity: %s", self.device)
        try:
            await self.device.async_update()
        except FlussApiClientCommunicationError:
            _LOGGER.error("Failed to update device: %s", self.device)
