"""Telegram bot notification entity."""

from typing import Any

from homeassistant.components.notify import (
    NotifyEntity,
    NotifyEntityDescription,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TelegramBotConfigEntry
from .const import ATTR_TITLE, CONF_CHAT_ID
from .entity import TelegramBotEntity


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


class TelegramBotNotifyEntity(TelegramBotEntity, NotifyEntity):
    """Representation of a telegram bot notification entity."""

    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(
        self,
        config_entry: TelegramBotConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize a notification entity."""
        super().__init__(
            config_entry, NotifyEntityDescription(key=subentry.data[CONF_CHAT_ID])
        )
        self.chat_id = subentry.data[CONF_CHAT_ID]
        self.name = subentry.title

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        kwargs: dict[str, Any] = {ATTR_TITLE: title}
        await self.service.send_message(message, self.chat_id, self._context, **kwargs)
