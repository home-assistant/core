"""Telegram media source."""
from __future__ import annotations

from functools import partial
from io import BytesIO
import mimetypes
from typing import TYPE_CHECKING, Dict, TypedDict

from aiohttp import web
import telegram
from yarl import URL

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
    generate_media_source_id as ms_generate_media_source_id,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import get_url

from .const import DOMAIN


class MediaSourceOptions(TypedDict):
    """Media source options."""
    # telefram.File identifier:
    file_id: str
    # Play_Media needs the mime and telegram provides it
    mime_type: str
    # The bot platform (polling/webhooks)
    # is currently an identifier of the bot that
    # is used. We need the bot to refresh the
    # download token.
    bot_platform: str



class TelegramManager:
    def __init__(self, hass):
        self.hass = hass
        self.bots: Dict[str, telegram.Bot] = {}
        self.mem_cache = {}
        self.mem_cache_entries = deque([], maxlen=5)
        # prepare local media directory
        # cleanup job to rm older files?

    def _generate_cache_key(self, media: MediaSourceOptions) -> str:
        return media["file_id"]

    async def async_get_url(self, media: MediaSourceOptions) -> str:
        """Get URL for play message.
        This method is a coroutine.
        """
        cache_key = self._generate_cache_key(media)
        # Is file already in memory
        if cache_key in self.mem_cache:
            filename = media["file_id"]
        else:
            filename = await self.hass.async_add_executor_job(
                partial(self._download_file, media=media)
            )
        return get_url(self.hass) + f"/api/telegram_proxy/{filename}"

    def _download_file(self, media) -> str:
        bot = self.bots[media["bot_platform"]]
        file = bot.get_file(file_id=media["file_id"])
        mime_type = media["mime_type"]
        data = BytesIO()
        file.download(out=data)
        # evict oldest if deque is full:
        if len(self.mem_cache_entries) == self.mem_cache_entries.maxlen:
            to_remove = self.mem_cache_entries.popleft()
            del self.mem_cache[to_remove]
        self.mem_cache_entries.append(media["file_id"])
        self.mem_cache[media["file_id"]] = (mime_type, data.getvalue())
        return media["file_id"]

    async def async_read_telegram_file(self, filename: str):
        try:
            (mime_type, data) = self.mem_cache[filename]
        except KeyError as err:
            raise Unresolvable(str(err)) from err
        return mime_type, data

async def async_get_media_source(hass: HomeAssistant) -> TelegramMediaSource:
    """Set up telegram media source."""
    return TelegramMediaSource(hass)

@callback
def generate_media_source_id(
    file_id: str,
    mime_type: str,
    bot_platform: str,
) -> str:
    """Generate a media source ID for telegram."""

    params = {
        "mime_type": mime_type,
        "bot_platform": bot_platform,
    }

    return ms_generate_media_source_id(
        DOMAIN,
        str(URL.build(path=file_id, query=params)),
    )

@callback
def media_source_id_to_kwargs(media_source_id: str) -> MediaSourceOptions:
    """Turn a media source ID into options."""
    parsed = URL(media_source_id)
    options = dict(parsed.query)
    try:
        kwargs: MediaSourceOptions = {
            "file_id": parsed.name,
            "mime_type": options.pop("mime_type"),
            "bot_platform": options.pop("bot_platform"),
        }
    except KeyError as exc:
        raise Unresolvable(f"No field specified: {str(exc)}") from exc
    return kwargs


class TelegramMediaSource(MediaSource):
    """A telegram-provided media source."""

    name: str = "Telegram"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize TelegramMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        manager: TelegramManager = self.hass.data[DOMAIN]
        try:
            media_args = media_source_id_to_kwargs(item.identifier)
            url = await manager.async_get_url(media_args)
        except HomeAssistantError as err:
            raise Unresolvable(str(err)) from err
        mime_type = media_args["mime_type"]
        return PlayMedia(url, mime_type)

class TelegramView(HomeAssistantView):
    """Telegram view to serve attached files and media."""

    requires_auth = False
    url = "/api/telegram_proxy/{filename}"
    name = "api:telegram_file"

    def __init__(self, manager: TelegramManager) -> None:
        """Initialize a telegram view."""
        self.manager = manager

    async def get(self, request: web.Request, filename: str) -> web.Response:
        """Start a get request."""
        try:
            content, data = await self.manager.async_read_telegram_file(filename)
        except HomeAssistantError as err:
            _LOGGER.error("Error on load telegram file: %s", err)
            return web.Response(status=HTTPStatus.NOT_FOUND)

        return web.Response(body=data, content_type=content)

