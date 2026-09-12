"""Data update coordinator for Podcast Player."""

import logging
from typing import override

from aiopodcast import Podcast, PodcastClient, PodcastFeedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class PodcastUpdateCoordinator(DataUpdateCoordinator[Podcast]):
    """Coordinate podcast feed updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[PodcastUpdateCoordinator],
        client: PodcastClient,
    ) -> None:
        """Initialize the podcast feed coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )
        self.entry = entry
        self.client = client
        self.url = entry.data[CONF_URL]

    async def async_fetch(self) -> Podcast:
        """Fetch the configured podcast feed."""
        return await self.client.async_fetch(self.url)

    @override
    async def _async_update_data(self) -> Podcast:
        """Fetch the latest podcast feed."""
        try:
            return await self.async_fetch()
        except PodcastFeedError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="feed_unavailable",
            ) from err


type PodcastConfigEntry = ConfigEntry[PodcastUpdateCoordinator]
