"""Base entity for the Discord integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from . import DiscordConfigEntry
from .const import DOMAIN


class DiscordEntity(Entity):
    """Base class for Discord entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: DiscordConfigEntry,
        subentry: ConfigSubentry,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        self.config_entry = config_entry
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{config_entry.unique_id or config_entry.entry_id}"
            f"_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            name=config_entry.title,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Discord",
            identifiers={(DOMAIN, config_entry.unique_id or config_entry.entry_id)},
        )
