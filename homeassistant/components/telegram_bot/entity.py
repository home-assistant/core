"""Base entity for Telegram bot integration."""

import telegram

from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from . import TelegramBotConfigEntry
from .const import DOMAIN


def bot_device_info(config_entry: TelegramBotConfigEntry, bot_id: int) -> DeviceInfo:
    """Return device info for the shared bot device."""
    return DeviceInfo(
        name=config_entry.title,
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="Telegram",
        model=config_entry.data[CONF_PLATFORM].capitalize(),
        sw_version=telegram.__version__,
        identifiers={(DOMAIN, f"{bot_id}")},
    )


class TelegramBotEntity(Entity):
    """Base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: TelegramBotConfigEntry,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""

        self.bot_id = config_entry.runtime_data.bot.id
        self.config_entry = config_entry
        self.entity_description = entity_description
        self.service = config_entry.runtime_data

        self._attr_unique_id = f"{self.bot_id}_{entity_description.key}"
        self._attr_device_info = bot_device_info(config_entry, self.bot_id)
