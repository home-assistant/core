"""Discord platform for notify component."""

from __future__ import annotations

from io import BytesIO
import logging
import os.path
from typing import Any, cast

import nextcord
from nextcord.abc import Messageable

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_EMBED = "embed"
ATTR_EMBED_AUTHOR = "author"
ATTR_EMBED_COLOR = "color"
ATTR_EMBED_DESCRIPTION = "description"
ATTR_EMBED_FIELDS = "fields"
ATTR_EMBED_FOOTER = "footer"
ATTR_EMBED_TITLE = "title"
ATTR_EMBED_THUMBNAIL = "thumbnail"
ATTR_EMBED_IMAGE = "image"
ATTR_EMBED_URL = "url"
ATTR_IMAGES = "images"
ATTR_URLS = "urls"
ATTR_VERIFY_SSL = "verify_ssl"

MAX_ALLOWED_DOWNLOAD_SIZE_BYTES = 8000000


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> DiscordNotificationService | None:
    """Get the Discord notification service."""
    if discovery_info is None:
        return None
    return DiscordNotificationService(hass, discovery_info[CONF_API_TOKEN])


class DiscordNotificationService(BaseNotificationService):
    """Implement the notification service for Discord."""

    def __init__(self, hass: HomeAssistant, token: str) -> None:
        """Initialize the service."""
        self.token = token
        self.hass = hass

    def file_exists(self, filename: str) -> bool:
        """Check if a file exists on disk and is in authorized path."""
        if not self.hass.config.is_allowed_path(filename):
            _LOGGER.warning("Path not allowed: %s", filename)
            return False
        if not os.path.isfile(filename):
            _LOGGER.warning("Not a file: %s", filename)
            return False
        return True

    async def async_get_file_from_url(
        self, url: str, verify_ssl: bool, max_file_size: int
    ) -> bytearray | None:
        """Retrieve file bytes from URL."""
        if not self.hass.config.is_allowed_external_url(url):
            _LOGGER.error("URL not allowed: %s", url)
            return None

        session = async_get_clientsession(self.hass)

        async with session.get(
            url,
            ssl=verify_ssl,
            timeout=30,
            raise_for_status=True,
        ) as resp:
            content_length = resp.headers.get("Content-Length")

            if content_length is not None and int(content_length) > max_file_size:
                _LOGGER.error(
                    (
                        "Attachment too large (Content-Length reports %s). Max size: %s"
                        " bytes"
                    ),
                    int(content_length),
                    max_file_size,
                )
                return None

            file_size = 0
            byte_chunks = bytearray()

            async for byte_chunk, _ in resp.content.iter_chunks():
                file_size += len(byte_chunk)
                if file_size > max_file_size:
                    _LOGGER.error(
                        "Attachment too large (Stream reports %s). Max size: %s bytes",
                        file_size,
                        max_file_size,
                    )
                    return None

                byte_chunks.extend(byte_chunk)

            return byte_chunks

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Login to Discord, send message to channel(s) and log out."""
        nextcord.VoiceClient.warn_nacl = False
        discord_bot = nextcord.Client()
        images = []
        embedding = None

        if ATTR_TARGET not in kwargs:
            _LOGGER.error("No target specified")
            return None

        data = kwargs.get(ATTR_DATA) or {}

        embeds: list[nextcord.Embed] = []
        if ATTR_EMBED in data:
            embedding = data[ATTR_EMBED]
            title = embedding.get(ATTR_EMBED_TITLE)
            description = embedding.get(ATTR_EMBED_DESCRIPTION)
            color = embedding.get(ATTR_EMBED_COLOR)
            url = embedding.get(ATTR_EMBED_URL)
            fields = embedding.get(ATTR_EMBED_FIELDS) or []

            if embedding:
                embed = nextcord.Embed(
                    title=title, description=description, color=color, url=url
                )
                for field in fields:
                    embed.add_field(**field)
                if ATTR_EMBED_FOOTER in embedding:
                    embed.set_footer(**embedding[ATTR_EMBED_FOOTER])
                if ATTR_EMBED_AUTHOR in embedding:
                    embed.set_author(**embedding[ATTR_EMBED_AUTHOR])
                if ATTR_EMBED_THUMBNAIL in embedding:
                    embed.set_thumbnail(**embedding[ATTR_EMBED_THUMBNAIL])
                if ATTR_EMBED_IMAGE in embedding:
                    embed.set_image(**embedding[ATTR_EMBED_IMAGE])
                embeds.append(embed)

        if ATTR_IMAGES in data:
            for image in data.get(ATTR_IMAGES, []):
                image_exists = await self.hass.async_add_executor_job(
                    self.file_exists, image
                )

                filename = os.path.basename(image)

                if image_exists:
                    images.append((image, filename))

        if ATTR_URLS in data:
            for url in data.get(ATTR_URLS, []):
                file = await self.async_get_file_from_url(
                    url,
                    data.get(ATTR_VERIFY_SSL, True),
                    MAX_ALLOWED_DOWNLOAD_SIZE_BYTES,
                )

                if file is not None:
                    filename = os.path.basename(url)

                    images.append((BytesIO(file), filename))

        await discord_bot.login(self.token)

        try:
            for channelid in kwargs[ATTR_TARGET]:
                channelid = int(channelid)
                # Must create new instances of File for each channel.
                files = [nextcord.File(image, filename) for image, filename in images]
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
