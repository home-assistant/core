"""DataUpdateCoordinator for the YouTube integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from youtubeaio.helper import first
from youtubeaio.types import UnauthorizedError, YouTubeBackendError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON, ATTR_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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


class YouTubeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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
        youtube = await self._auth.get_resource()
        res = {}
        channel_ids = self.config_entry.options[CONF_CHANNELS]
        try:
            async for channel in youtube.get_channels(channel_ids):
                video = await first(
                    youtube.get_playlist_items(channel.upload_playlist_id, 1)
                )
                latest_video = None
                if video:
                    latest_video = {
                        ATTR_PUBLISHED_AT: video.snippet.added_at,
                        ATTR_TITLE: video.snippet.title,
                        ATTR_DESCRIPTION: video.snippet.description,
                        ATTR_THUMBNAIL: video.snippet.thumbnails.get_highest_quality().url,
                        ATTR_VIDEO_ID: video.content_details.video_id,
                    }
                res[channel.channel_id] = {
                    ATTR_ID: channel.channel_id,
                    ATTR_TITLE: channel.snippet.title,
                    ATTR_ICON: channel.snippet.thumbnails.get_highest_quality().url,
                    ATTR_LATEST_VIDEO: latest_video,
                    ATTR_SUBSCRIBER_COUNT: channel.statistics.subscriber_count,
                }
        except UnauthorizedError as err:
            raise ConfigEntryAuthFailed from err
        except YouTubeBackendError as err:
            raise UpdateFailed("Couldn't connect to YouTube") from err
        return res
