"""The Podcast Player integration."""

from aiopodcast import PodcastConnectionError, PodcastFeedError, PodcastHTTPError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .client import create_client
from .const import DOMAIN
from .coordinator import PodcastConfigEntry, PodcastUpdateCoordinator

PLATFORMS = [Platform.EVENT]


async def async_setup_entry(hass: HomeAssistant, entry: PodcastConfigEntry) -> bool:
    """Set up a podcast feed from a config entry."""
    client = create_client(hass)
    coordinator = PodcastUpdateCoordinator(hass, entry, client)

    try:
        podcast = await coordinator.async_fetch()
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

    coordinator.async_set_updated_data(podcast)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PodcastConfigEntry) -> bool:
    """Unload a podcast feed config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
