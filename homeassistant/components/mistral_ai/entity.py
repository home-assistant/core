"""Base entity for Mistral AI."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import CONF_CHAT_MODEL, DEFAULT, DOMAIN

if TYPE_CHECKING:
    from . import MistralAIConfigEntry


class MistralEntity(Entity):
    """Base entity shared by all Mistral AI platforms."""

    _attr_has_entity_name = True
    _attr_name: str | None = None

    def __init__(self, entry: MistralAIConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Mistral",
            model=subentry.data.get(CONF_CHAT_MODEL, DEFAULT[CONF_CHAT_MODEL]),
            entry_type=dr.DeviceEntryType.SERVICE,
        )
