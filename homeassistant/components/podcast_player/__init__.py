"""The Podcast Player integration."""

import asyncio
from dataclasses import dataclass, field

from aiopodcast import (
    Podcast,
    PodcastClient,
    PodcastConnectionError,
    PodcastFeedError,
    PodcastHTTPError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .client import create_client
from .const import DOMAIN


@dataclass(slots=True)
class PodcastRuntimeData:
    """Runtime data for a podcast feed."""

    client: PodcastClient
    url: str
    podcast: Podcast
    _refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def async_refresh(self) -> Podcast:
        """Fetch the latest podcast feed."""
        async with self._refresh_lock:
            self.podcast = await self.client.async_fetch(self.url)
            return self.podcast


type PodcastConfigEntry = ConfigEntry[PodcastRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: PodcastConfigEntry) -> bool:
    """Set up a podcast feed from a config entry."""
    client = create_client(hass)

    try:
        podcast = await client.async_fetch(entry.data[CONF_URL])
    except (PodcastConnectionError, PodcastHTTPError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="feed_unavailable",
        ) from err
    except PodcastFeedError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_feed",
        ) from err

    entry.runtime_data = PodcastRuntimeData(
        client=client,
        url=entry.data[CONF_URL],
        podcast=podcast,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PodcastConfigEntry) -> bool:
    """Unload a podcast feed config entry."""
    return True
