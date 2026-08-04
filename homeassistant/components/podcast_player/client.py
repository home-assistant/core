"""Client helpers for Podcast Player."""

from aiopodcast import PodcastClient

from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


def create_client(hass: HomeAssistant) -> PodcastClient:
    """Create a podcast client using Home Assistant's shared web session."""
    return PodcastClient(
        async_get_clientsession(hass),
        headers={
            "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml",
            "User-Agent": f"HomeAssistant/{__version__}",
        },
    )
