"""Base entities for the Fluss+ integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity, EntityDescription

from .button import FlussButton
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FlussEntity(Entity):
    """Base class for Fluss entities."""

    _attr_has_entity_name = True

    def __init__(  # noqa: D107
        self,
        hass: HomeAssistant,
        device: FlussButton,
        entry: ConfigEntry,
        entity_description: EntityDescription,
        unique_id_suffix: str | None = None,
    ) -> None:
        """Initialize the entity."""
        self.hass = hass
        self.device = device
        self.entry = entry
        self.entity_description = entity_description

        unique_id = device.unique_id or "default_unique_id"
        self.identifiers = ({(DOMAIN, unique_id)},)
        self._attr_unique_id = unique_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_id)},
        }

        if unique_id_suffix is None:
            self._attr_unique_id = (
                f"{entry.data[CONF_ADDRESS]}_{entity_description.key}"
            )

    def _update_entry_data(self) -> None:
        """Update the entry data if necessary."""
        if (
            CONF_ADDRESS not in self.entry.data
            or self.entry.data[CONF_ADDRESS] != self.device.unique_id
        ):
            data = dict(self.entry.data)
            data[CONF_ADDRESS] = self.device.unique_id or "default_unique_id"
            self.hass.config_entries.async_update_entry(self.entry, data=data)

    async def async_update(self):
        """Fetch new state data for the entity."""
        _LOGGER.debug("Updating FlussEntity: %s", self.device)
        await self.device.async_update()
