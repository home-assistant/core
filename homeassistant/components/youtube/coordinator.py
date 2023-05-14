"""DataUpdateCoordinator for the YouTube integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from googleapiclient.discovery import Resource
from googleapiclient.http import HttpRequest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import AsyncConfigEntryAuth
from .const import CONF_CHANNELS, DOMAIN, LOGGER


def get_upload_playlist_id(channel_id: str) -> str:
    """Return the playlist id with the uploads of the channel.

    Replacing the UC in the channel id (UCxxxxxxxxxxxx) with UU is the way to do it without extra request (UUxxxxxxxxxxxx).
    """
    return channel_id.replace("UC", "UU", 1)


class YouTubeDataUpdateCoordinator(DataUpdateCoordinator):
    """A YouTube Data Update Coordinator."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, auth: AsyncConfigEntryAuth
    ) -> None:
        """Initialize the YouTube data coordinator."""
        self.entry = entry
        self._auth = auth
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        data = {}
        service = await self._auth.get_resource()
        channels = self.entry.options[CONF_CHANNELS]
        channel_request: HttpRequest = service.channels().list(
            part="snippet,statistics", id=",".join(channels), maxResults=50
        )
        response: dict = await self.hass.async_add_executor_job(channel_request.execute)

        async def _compile_data(channel: dict[str, Any]) -> None:
            data[channel["id"]] = {
                "id": channel["id"],
                "title": channel["snippet"]["title"],
                "icon": channel["snippet"]["thumbnails"]["high"]["url"],
                "latest_video": await self._get_latest_video(service, channel["id"]),
                "subscriber_count": int(channel["statistics"]["subscriberCount"]),
            }

        await asyncio.gather(*[_compile_data(channel) for channel in response["items"]])
        return data

    async def _get_latest_video(
        self, service: Resource, channel_id: str
    ) -> dict[str, Any]:
        playlist_id = get_upload_playlist_id(channel_id)
        response: dict = (
            service.playlistItems()
            .list(part="snippet,contentDetails", playlistId=playlist_id, maxResults=1)
            .execute()
        )
        video = response["items"][0]
        return {
            "published_at": video["snippet"]["publishedAt"],
            "title": video["snippet"]["title"],
            "description": video["snippet"]["description"],
            "thumbnail": video["snippet"]["thumbnails"]["standard"]["url"],
            "video_id": video["contentDetails"]["videoId"],
        }
