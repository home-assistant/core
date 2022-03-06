"""Discord platform for notify component."""
from __future__ import annotations

import logging
import os.path
from typing import Any, cast

import nextcord
from nextcord.abc import Messageable
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_EMBED = "embed"
ATTR_EMBED_AUTHOR = "author"
ATTR_EMBED_FIELDS = "fields"
ATTR_EMBED_FOOTER = "footer"
ATTR_EMBED_THUMBNAIL = "thumbnail"
ATTR_IMAGES = "images"

# Deprecated in Home Assistant 2022.4
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_TOKEN): cv.string})


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> DiscordNotificationService:
    """Get the NFAndroidTV notification service."""
    if discovery_info is not None:
        return DiscordNotificationService(hass, discovery_info[CONF_TOKEN])
    return DiscordNotificationService(hass, config[CONF_TOKEN])


class DiscordNotificationService(BaseNotificationService):
    """Implement the notification service for Discord."""

    def __init__(self, hass: HomeAssistant, token: str) -> None:
        """Initialize the service."""
        self.token = token
        self.hass = hass

    def file_exists(self, filename: str) -> bool:
        """Check if a file exists on disk and is in authorized path."""
        if not self.hass.config.is_allowed_path(filename):
            return False
        return os.path.isfile(filename)

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Login to Discord, send message to channel(s) and log out."""
        nextcord.VoiceClient.warn_nacl = False
        discord_bot = nextcord.Client()
        images = None
        embedding = None

        if ATTR_TARGET not in kwargs:
            _LOGGER.error("No target specified")
            return None

        data = kwargs.get(ATTR_DATA) or {}

        embeds: list[nextcord.Embed] = []
        if ATTR_EMBED in data:
            embedding = data[ATTR_EMBED]
            fields = embedding.get(ATTR_EMBED_FIELDS) or []

            if embedding:
                embed = nextcord.Embed(**embedding)
                for field in fields:
                    embed.add_field(**field)
                if ATTR_EMBED_FOOTER in embedding:
                    embed.set_footer(**embedding[ATTR_EMBED_FOOTER])
                if ATTR_EMBED_AUTHOR in embedding:
                    embed.set_author(**embedding[ATTR_EMBED_AUTHOR])
                if ATTR_EMBED_THUMBNAIL in embedding:
                    embed.set_thumbnail(**embedding[ATTR_EMBED_THUMBNAIL])
                embeds.append(embed)

        if ATTR_IMAGES in data:
            images = []

            for image in data.get(ATTR_IMAGES, []):
                image_exists = await self.hass.async_add_executor_job(
                    self.file_exists, image
                )

                if image_exists:
                    images.append(image)
                else:
                    _LOGGER.warning("Image not found: %s", image)

        await discord_bot.login(self.token)

        try:
            for channelid in kwargs[ATTR_TARGET]:
                channelid = int(channelid)
                # Must create new instances of File for each channel.
                files = [nextcord.File(image) for image in images] if images else []
                try:
                    channel = cast(
                        Messageable, await discord_bot.fetch_channel(channelid)
                    )
                except nextcord.NotFound:
                    try:
                        channel = await discord_bot.fetch_user(channelid)
                    except nextcord.NotFound:
                        _LOGGER.warning("Channel not found for ID: %s", channelid)
                        continue
                await channel.send(message, files=files, embeds=embeds)
        except (nextcord.HTTPException, nextcord.NotFound) as error:
            _LOGGER.warning("Communication error: %s", error)
        await discord_bot.close()
