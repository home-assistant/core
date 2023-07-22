"""DataUpdateCoordinator for the YouTube integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from youtubeaio.helper import first
from youtubeaio.models import YouTubeChannel, YouTubePlaylistItem

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import AsyncConfigEntryAuth
from .const import (
    CONF_CHANNELS,
    DOMAIN,
    LOGGER,
)


@dataclass
class YouTubeHAData:
    """Data holder for channels."""

    channel: YouTubeChannel
    latest_video: YouTubePlaylistItem | None


class YouTubeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, YouTubeHAData]]):
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

    async def _async_update_data(self) -> dict[str, YouTubeHAData]:
        youtube = await self._auth.get_resource()
        res = {}
        channel_ids = self.config_entry.options[CONF_CHANNELS]
        async for channel in youtube.get_channels(channel_ids):
            latest_video = await first(
                youtube.get_playlist_items(channel.upload_playlist_id, 1)
            )
            res[channel.channel_id] = YouTubeHAData(
                channel=channel,
                latest_video=latest_video,
            )
        return res
