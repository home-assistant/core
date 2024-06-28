"""Base entities for the Motionblinds Bluetooth integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.entity import Entity, EntityDescription

from .device import FlussButton

_LOGGER = logging.getLogger(__name__)


class FlussEntity(Entity):
    """Base class for Fluss entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    device: FlussButton
    entry: ConfigEntry

    def __init__(
        self,
        device: FlussButton,
        entry: ConfigEntry,
        entity_description: EntityDescription,
        unique_id_suffix: str | None = None,
    ) -> None:
        """Initialize the entity."""
        if unique_id_suffix is None:
            self._attr_unique_id = entry.data[CONF_ADDRESS]
        else:
            self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{unique_id_suffix}"
        self.device = device
        self.entry = entry
        self.entity_description = entity_description

    async def async_update(self) -> None:
        """Update state, called by HA if there is a poll interval and by the service homeassistant.update_entity."""
        # _LOGGER.debug("(%s) Updating entity", self.entry.data[])
        # await self.device.status_query()
