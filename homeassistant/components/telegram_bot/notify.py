"""Telegram bot notification entity."""

from typing import Any

import telegram

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TelegramBotConfigEntry
from .const import ATTR_TITLE, CONF_CHAT_ID, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TelegramBotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the telegram bot notification entity platform."""

    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [TelegramBotNotifyEntity(config_entry, subentry)],
            config_subentry_id=subentry_id,
        )


class TelegramBotNotifyEntity(NotifyEntity):
    """Representation of a telegram bot notification entity."""

    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(
        self,
        config_entry: TelegramBotConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize a notification entity."""
        bot_id = config_entry.runtime_data.bot.id
        chat_id = subentry.data[CONF_CHAT_ID]

        self._attr_unique_id = f"{bot_id}_{chat_id}"
        self.name = subentry.title

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Telegram",
            model=config_entry.data[CONF_PLATFORM].capitalize(),
            sw_version=telegram.__version__,
            identifiers={(DOMAIN, f"{bot_id}")},
        )
        self._target = chat_id
        self._service = config_entry.runtime_data

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        kwargs: dict[str, Any] = {ATTR_TITLE: title}
        await self._service.send_message(message, self._target, self._context, **kwargs)
