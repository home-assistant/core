"""The krisinformation integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up krisinformation from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    # 1. Create API instance
    # 2. Validate the API connection (and authentication)
    # 3. Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


# GEO-LOCATION
from aio_geojson_client.feed import GeoJsonFeed
from aio_geojson_client.feed_entry import FeedEntry
from aio_geojson_client.feed_manager import FeedManagerBase


class KrisinformationFeedManager(FeedManagerBase):
    """Feed Manager for Krisinformation.se feed."""

    def __init__(
        self,
        generate_callback,
        update_callback,
        remove_callback,
        coordinates,
        filter_radius=None,
        filter_categories=None,
    )-> None:
        """Initialize the Krisinformation.se Feed Manager."""
        feed = KrisinformationFeed(
            coordinates,
            filter_radius=filter_radius,
            filter_categories=filter_categories,
        )
        super().__init__(feed, generate_callback, update_callback, remove_callback)


class KrisinformationFeed(GeoJsonFeed):
    """Krisinformation.se feed."""

    def __init__(
        self,
        home_coordinates,
        filter_radius=None,
        filter_categories=None,
    )-> None:
        """Initialise this service."""
        super().__init__(
            home_coordinates,
            "https://api.krisinformation.se/v2/feed?format=geojson",
            filter_radius=filter_radius,
            filter_categories=filter_categories,
        )

    def _new_entry(self, home_coordinates, feature, global_data):
        """Generate a new entry."""
        return KrisinformationFeedEntry(home_coordinates, feature, global_data)


class KrisinformationFeedEntry(FeedEntry):
    """Krisinformation.se feed entry."""
