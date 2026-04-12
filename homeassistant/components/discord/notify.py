"""Discord notification entity."""

from __future__ import annotations

import logging
from typing import cast

import nextcord
from nextcord.abc import Messageable

from homeassistant.components.notify import (
    NotifyEntity,
    NotifyEntityDescription,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DiscordConfigEntry
from .const import CONF_CHANNEL_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DiscordConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Discord notify entities from a config entry."""
    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [DiscordNotifyEntity(config_entry, subentry)],
            config_subentry_id=subentry_id,
        )


class DiscordNotifyEntity(NotifyEntity):
    """Discord notification entity for a single channel or DM."""

    _attr_has_entity_name = True
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(
        self,
        config_entry: DiscordConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the Discord notify entity."""
        self.config_entry = config_entry
        self.entity_description = NotifyEntityDescription(
            key=str(subentry.data[CONF_CHANNEL_ID])
        )
        self._channel_id: int = subentry.data[CONF_CHANNEL_ID]
        self._attr_name = subentry.title
        self._attr_unique_id = (
            f"{config_entry.unique_id or config_entry.entry_id}"
            f"_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            name=config_entry.title,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Discord",
            identifiers={(DOMAIN, config_entry.unique_id or config_entry.entry_id)},
        )

    async def _async_get_messageable(self, discord_bot: nextcord.Client) -> Messageable:
        """Fetch the target channel or DM user for this entity."""
        try:
            return cast(
                Messageable,
                await discord_bot.fetch_channel(self._channel_id),
            )
        except nextcord.NotFound:
            try:
                return cast(Messageable, await discord_bot.fetch_user(self._channel_id))
            except nextcord.NotFound as ex:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="channel_not_found",
                    translation_placeholders={"channel_id": str(self._channel_id)},
                ) from ex

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a text message to the configured Discord channel or user DM."""
        nextcord.VoiceClient.warn_nacl = False
        discord_bot = nextcord.Client()
        try:
            await discord_bot.login(self.config_entry.runtime_data)
            channel = await self._async_get_messageable(discord_bot)
            content = f"**{title}**\n{message}" if title else message
            await channel.send(content)
        except (nextcord.HTTPException, nextcord.NotFound) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_failed",
                translation_placeholders={"error": str(ex)},
            ) from ex
        finally:
            await discord_bot.close()
