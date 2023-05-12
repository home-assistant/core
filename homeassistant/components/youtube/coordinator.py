"""DataUpdateCoordinator for the YouTube integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from googleapiclient.http import HttpRequest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import AsyncConfigEntryAuth
from .const import CONF_CHANNELS, DOMAIN, LOGGER


class YouTubeDataUpdateCoordinator(DataUpdateCoordinator):
    """A YouTube Data Update Coordinator."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, auth: AsyncConfigEntryAuth
    ) -> None:
        """Initialize the Yale hub."""
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
        for channel in response["items"]:
            data[channel["id"]] = {
                "id": channel["id"],
                "title": channel["snippet"]["title"],
                "icon": channel["snippet"]["thumbnails"]["high"]["url"],
                "latest_video": await self._get_latest_video(channel["id"]),
                "subscriber_count": int(channel["statistics"]["subscriberCount"]),
            }
        return data

    async def _get_latest_video(self, channel_id: str) -> dict[str, Any]:
        service = await self._auth.get_resource()
        playlist_id = channel_id.replace("UC", "UU", 1)
        playlist_request: HttpRequest = service.playlistItems().list(
            part="snippet,contentDetails", playlistId=playlist_id
        )
        response: dict = await self.hass.async_add_executor_job(
            playlist_request.execute
        )
        video = response["items"][0]
        return {
            "published_at": video["snippet"]["publishedAt"],
            "title": video["snippet"]["title"],
            "description": video["snippet"]["description"],
            "thumbnail": video["snippet"]["thumbnails"]["standard"]["url"],
            "video_id": video["contentDetails"]["videoId"],
        }
