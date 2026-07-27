"""Telegram bot notification entity."""

from typing import Any, override

from homeassistant.components.notify import (
    NotifyEntity,
    NotifyEntityDescription,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TelegramBotConfigEntry
from .const import ATTR_TITLE, CONF_CHAT_ID, DOMAIN
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

    _attr_name = None
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
        # Each chat gets its own device (keyed per chat) linked to the shared bot device.
        device_info = self._attr_device_info
        assert device_info is not None
        device_info["identifiers"] = {(DOMAIN, f"{self.bot_id}_{self.chat_id}")}
        device_info["name"] = subentry.title
        device_info["via_device"] = (DOMAIN, f"{self.bot_id}")

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        kwargs: dict[str, Any] = {ATTR_TITLE: title}
        await self.service.send_message(message, self.chat_id, self._context, **kwargs)
