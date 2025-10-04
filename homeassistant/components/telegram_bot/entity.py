"""Base entity for Telegram bot integration."""

import telegram

from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import TelegramBotConfigEntry
from .const import DOMAIN


class TelegramBotEntity(Entity):
    """Base entity."""

    def __init__(self, config_entry: TelegramBotConfigEntry) -> None:
        """Initialize the entity."""

        self.bot_id = config_entry.runtime_data.bot.id
        self.config_entry = config_entry
        self.service = config_entry.runtime_data

        self._attr_device_info = DeviceInfo(
            name=config_entry.title,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Telegram",
            model=config_entry.data[CONF_PLATFORM].capitalize(),
            sw_version=telegram.__version__,
            identifiers={(DOMAIN, f"{self.bot_id}")},
        )
