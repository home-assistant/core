"""DataUpdateCoordinator for the KEF integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

import aiohttp
from pykefcontrol.kef_connector import KefAsyncConnector

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

type KefConfigEntry = ConfigEntry[KefCoordinator]


@dataclass
class KefData:
    """Data from a KEF speaker update."""

    is_on: bool
    source: str
    volume: int
    is_playing: bool
    media_title: str | None = None
    media_artist: str | None = None
    media_album: str | None = None
    media_image_url: str | None = None


class KefCoordinator(DataUpdateCoordinator[KefData]):
    """KEF speaker data update coordinator."""

    config_entry: KefConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: KefConfigEntry,
        connector: KefAsyncConnector,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"KEF {config_entry.title}",
            update_interval=SCAN_INTERVAL,
        )
        self.connector = connector

    @override
    async def _async_update_data(self) -> KefData:
        """Fetch data from the KEF speaker."""
        try:
            source = await self.connector.source
            volume = await self.connector.volume
            is_on = source != "standby"
            is_playing = False
            media_title = None
            media_artist = None
            media_album = None
            media_image_url = None

            if is_on:
                is_playing = await self.connector.is_playing
                song_info = await self.connector.get_song_information()
                media_title = song_info.get("title")
                media_artist = song_info.get("artist")
                media_album = song_info.get("album")
                media_image_url = song_info.get("cover_url")

        except (aiohttp.ClientError, TimeoutError, IndexError, KeyError) as err:
            raise UpdateFailed(f"Error communicating with KEF speaker: {err}") from err

        return KefData(
            is_on=is_on,
            source=source,
            volume=volume,
            is_playing=is_playing,
            media_title=media_title,
            media_artist=media_artist,
            media_album=media_album,
            media_image_url=media_image_url,
        )
