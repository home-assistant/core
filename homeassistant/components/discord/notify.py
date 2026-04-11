"""Discord notification entity."""

from __future__ import annotations

from io import BytesIO
import logging
import os.path
from typing import cast
from urllib.parse import urlparse

import aiohttp
import nextcord
from nextcord.abc import Messageable
import voluptuous as vol

from homeassistant.components.notify import (
    NotifyEntity,
    NotifyEntityDescription,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import VolDictType

from . import DiscordConfigEntry
from .const import CONF_CHANNEL_ID, DOMAIN
from .entity import DiscordEntity

_LOGGER = logging.getLogger(__name__)

MAX_ALLOWED_DOWNLOAD_SIZE_BYTES = 8_000_000

PARALLEL_UPDATES = 0

SERVICE_SEND_MESSAGE = "send_message"
ATTR_IMAGES = "images"
ATTR_URLS = "urls"
ATTR_VERIFY_SSL = "verify_ssl"
ATTR_EMBED = "embed"

DISCORD_SERVICE_SCHEMA: VolDictType = {
    vol.Required("message"): cv.string,
    vol.Optional("title"): cv.string,
    vol.Optional(ATTR_IMAGES, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_URLS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_VERIFY_SSL, default=True): cv.boolean,
    vol.Optional(ATTR_EMBED): dict,
}


def _register_entity_services() -> None:
    """Register entity services for the Discord notify platform."""
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SEND_MESSAGE,
        DISCORD_SERVICE_SCHEMA,
        "_async_handle_send_message_service",
    )


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

    _register_entity_services()


class DiscordNotifyEntity(DiscordEntity, NotifyEntity):
    """Discord notification entity for a single channel or DM."""

    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(
        self,
        config_entry: DiscordConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the Discord notify entity."""
        super().__init__(
            config_entry,
            subentry,
            NotifyEntityDescription(key=str(subentry.data[CONF_CHANNEL_ID])),
        )
        self._channel_id: int = subentry.data[CONF_CHANNEL_ID]
        self._attr_name = subentry.title

    def _file_exists(self, filename: str) -> bool:
        """Check if a file exists on disk and is in an allowed path.

        Raises HomeAssistantError with an actionable message if not.
        """
        if not self.hass.config.is_allowed_path(filename):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="path_not_allowed",
                translation_placeholders={"path": filename},
            )
        if not os.path.isfile(filename):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="file_not_found",
                translation_placeholders={"path": filename},
            )
        return True

    async def async_get_file_from_url(
        self, url: str, verify_ssl: bool, max_file_size: int
    ) -> bytearray | None:
        """Retrieve file bytes from a URL."""
        if not self.hass.config.is_allowed_external_url(url):
            _LOGGER.error("URL not allowed: %s", url)
            return None

        session = async_get_clientsession(self.hass)

        try:
            async with session.get(
                url,
                ssl=verify_ssl,
                timeout=aiohttp.ClientTimeout(total=30),
                raise_for_status=True,
            ) as resp:
                content_length = resp.headers.get("Content-Length")

                if content_length is not None and int(content_length) > max_file_size:
                    _LOGGER.error(
                        "Attachment too large (Content-Length reports %s). Max size: %s bytes",
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
                            "Attachment too large (stream reports %s). Max size: %s bytes",
                            file_size,
                            max_file_size,
                        )
                        return None

                    byte_chunks.extend(byte_chunk)

                return byte_chunks
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to download attachment from %s: %s", url, err)
            return None

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

    async def _async_handle_send_message_service(
        self,
        message: str,
        title: str | None = None,
        images: list[str] | None = None,
        urls: list[str] | None = None,
        verify_ssl: bool = True,
        embed: dict | None = None,
    ) -> None:
        """Handle the discord.send_message service call."""
        await self.async_send_message_with_attachments(
            message=message,
            title=title,
            images=images or [],
            urls=urls or [],
            verify_ssl=verify_ssl,
            embed=embed,
        )

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

    async def async_send_message_with_attachments(
        self,
        message: str,
        title: str | None = None,
        images: list[str] | None = None,
        urls: list[str] | None = None,
        verify_ssl: bool = True,
        embed: dict | None = None,
    ) -> None:
        """Send a rich message with optional file attachments and embed.

        This helper is intended for use by Discord-specific service actions.
        """
        files: list[nextcord.File] = []
        embeds: list[nextcord.Embed] = []

        for image_path in images or []:
            await self.hass.async_add_executor_job(self._file_exists, image_path)
            files.append(nextcord.File(image_path, os.path.basename(image_path)))

        for url in urls or []:
            file_bytes = await self.async_get_file_from_url(
                url, verify_ssl, MAX_ALLOWED_DOWNLOAD_SIZE_BYTES
            )
            if file_bytes is not None:
                filename = os.path.basename(urlparse(url).path) or "attachment"
                files.append(nextcord.File(BytesIO(file_bytes), filename))

        if embed:
            discord_embed = nextcord.Embed(
                title=embed.get("title"),
                description=embed.get("description"),
                color=embed.get("color"),
                url=embed.get("url"),
            )
            for field in embed.get("fields") or []:
                try:
                    discord_embed.add_field(**field)
                except TypeError:
                    _LOGGER.warning("Invalid embed field: %s", field)
            if "footer" in embed:
                discord_embed.set_footer(**embed["footer"])
            if "author" in embed:
                discord_embed.set_author(**embed["author"])
            if "thumbnail" in embed:
                discord_embed.set_thumbnail(**embed["thumbnail"])
            if "image" in embed:
                discord_embed.set_image(**embed["image"])
            embeds.append(discord_embed)

        nextcord.VoiceClient.warn_nacl = False
        discord_bot = nextcord.Client()
        try:
            await discord_bot.login(self.config_entry.runtime_data)
            channel = await self._async_get_messageable(discord_bot)
            content = f"**{title}**\n{message}" if title else message
            await channel.send(content, files=files, embeds=embeds)
        except (nextcord.HTTPException, nextcord.NotFound) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_failed",
                translation_placeholders={"error": str(ex)},
            ) from ex
        finally:
            await discord_bot.close()
