"""DataUpdateCoordinator for the YouTube integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from googleapiclient.discovery import Resource
from googleapiclient.http import HttpRequest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON, ATTR_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import AsyncConfigEntryAuth
from .const import (
    ATTR_DESCRIPTION,
    ATTR_LATEST_VIDEO,
    ATTR_PUBLISHED_AT,
    ATTR_SUBSCRIBER_COUNT,
    ATTR_THUMBNAIL,
    ATTR_TITLE,
    ATTR_VIDEO_ID,
    CONF_CHANNELS,
    DOMAIN,
    LOGGER,
)


def get_upload_playlist_id(channel_id: str) -> str:
    """Return the playlist id with the uploads of the channel.

    Replacing the UC in the channel id (UCxxxxxxxxxxxx) with UU is
    the way to do it without extra request (UUxxxxxxxxxxxx).
    """
    return channel_id.replace("UC", "UU", 1)


class YouTubeDataUpdateCoordinator(DataUpdateCoordinator):
    """A YouTube Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, auth: AsyncConfigEntryAuth) -> None:
        """Initialize the YouTube data coordinator."""
        self._auth = auth
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        service = await self._auth.get_resource()
        channels = await self._get_channels(service)

        return await self.hass.async_add_executor_job(
            self._get_channel_data, service, channels
        )

    async def _get_channels(self, service: Resource) -> list[dict[str, Any]]:
        data = []
        received_channels = 0
        channels = self.config_entry.options[CONF_CHANNELS]
        while received_channels < len(channels):
            # We're slicing the channels in chunks of 50 to avoid making the URI too long
            end = min(received_channels + 50, len(channels))
            channel_request: HttpRequest = service.channels().list(
                part="snippet,statistics",
                id=",".join(channels[received_channels:end]),
                maxResults=50,
            )
            response: dict = await self.hass.async_add_executor_job(
                channel_request.execute
            )
            data.extend(response["items"])
            received_channels += len(response["items"])
        return data

    def _get_channel_data(
        self, service: Resource, channels: list[dict[str, Any]]
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for channel in channels:
            playlist_id = get_upload_playlist_id(channel["id"])
            response = (
                service.playlistItems()
                .list(
                    part="snippet,contentDetails", playlistId=playlist_id, maxResults=1
                )
                .execute()
            )
            video = response["items"][0]
            data[channel["id"]] = {
                ATTR_ID: channel["id"],
                ATTR_TITLE: channel["snippet"]["title"],
                ATTR_ICON: channel["snippet"]["thumbnails"]["high"]["url"],
                ATTR_LATEST_VIDEO: {
                    ATTR_PUBLISHED_AT: video["snippet"]["publishedAt"],
                    ATTR_TITLE: video["snippet"]["title"],
                    ATTR_DESCRIPTION: video["snippet"]["description"],
                    ATTR_THUMBNAIL: self._get_thumbnail(video),
                    ATTR_VIDEO_ID: video["contentDetails"]["videoId"],
                },
                ATTR_SUBSCRIBER_COUNT: int(channel["statistics"]["subscriberCount"]),
            }
        return data

    def _get_thumbnail(self, video: dict[str, Any]) -> str | None:
        thumbnails = video["snippet"]["thumbnails"]
        for size in ("standard", "high", "medium", "default"):
            if size in thumbnails:
                return thumbnails[size]["url"]
        return None
