"""The Radio Browser integration."""
from __future__ import annotations

import mimetypes

from radios import FilterBy, RadioBrowser, RadioBrowserError, Station
import voluptuous as vol

from homeassistant.components.media_source.error import Unresolvable
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_FAVORITE_RADIOS,
    CONF_RADIO_BROWSER,
    DOMAIN,
    LAST_FAVORITE,
    SERVICE_NEXT_RADIO,
    SERVICE_PREV_RADIO,
    SERVICE_START_RADIO,
)
from .media_source import CODEC_TO_MIMETYPE

ATTR_PLAYER_ENTITY = "entity_id"
ATTR_FAVORITE = "favorite"
PLATFORMS = ["media_source"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_FAVORITE_RADIOS): cv.ensure_list,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_START_RADIO_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_FAVORITE): cv.positive_int,
        vol.Required(ATTR_PLAYER_ENTITY): cv.entity_id,
    }
)

SERVICE_NEXT_RADIO_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PLAYER_ENTITY): cv.entity_id,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the favorites list if it exists in configuration.yaml.

    The Configuration of the favorite radios looks like this:

    radio_browser:
        favorites:
            - 'Radio Swiss Classic'
            - 'Concertzender Jazz'

    """
    favorites = config[DOMAIN][CONF_FAVORITE_RADIOS]
    if hass.data.get(DOMAIN) is None:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][CONF_FAVORITE_RADIOS] = favorites
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Radio Browser from a config entry.

    This integration doesn't set up any enitites, as it provides a media source
    only.
    """
    session = async_get_clientsession(hass)
    radios = RadioBrowser(session=session, user_agent=f"HomeAssistant/{__version__}")

    try:
        await radios.stats()
    except RadioBrowserError as err:
        raise ConfigEntryNotReady("Could not connect to Radio Browser API") from err

    if hass.data.get(DOMAIN) is None:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][CONF_RADIO_BROWSER] = radios
    hass.data[DOMAIN][LAST_FAVORITE] = 0

    await async_setup_services(hass)
    return True


# Service Handlers for the radio services.


async def async_setup_services(hass: HomeAssistant) -> None:
    """Service handler setup."""

    async def try_play_radio(radios: RadioBrowser, station_name: str, player):
        stations = await radios.stations(
            filter_by=FilterBy.NAME_EXACT, filter_term=station_name
        )
        if stations is None:
            return
        station: Station = stations[0]
        mime_type = CODEC_TO_MIMETYPE.get(station.codec)
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(station.url)
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": player,
                "media_content_id": station.url_resolved,
                "media_content_type": mime_type,
                "extra": {"title": station.name, "thumb": station.favicon},
            },
            False,
        )

    async def start_radio(service):
        """Start radio on specified player entity."""
        idx = service.data[ATTR_FAVORITE]
        player = service.data.get(ATTR_PLAYER_ENTITY)
        radios: RadioBrowser = hass.data[DOMAIN][CONF_RADIO_BROWSER]
        favorites = hass.data[DOMAIN][CONF_FAVORITE_RADIOS]

        if radios is None:
            raise Unresolvable("Radio Browser not initialized")

        if idx >= len(favorites) or idx < 0:
            return

        try_play_radio(radios, favorites[idx], player)
        hass.data[DOMAIN][LAST_FAVORITE] = idx

    async def next_radio(service):
        """Switch Radio to the next favorite."""
        player = service.data.get(ATTR_PLAYER_ENTITY)
        radios: RadioBrowser = hass.data[DOMAIN][CONF_RADIO_BROWSER]
        favorites = hass.data[DOMAIN][CONF_FAVORITE_RADIOS]

        idx: int = hass.data[DOMAIN][LAST_FAVORITE]

        idx = idx + 1
        idx = min(idx, len(favorites) - 1)
        idx = max(idx, 0)

        try_play_radio(radios, favorites[idx], player)
        hass.data[DOMAIN][LAST_FAVORITE] = idx

    async def prev_radio(service):
        """Switch radio to previous favorite."""
        player = service.data.get(ATTR_PLAYER_ENTITY)
        radios: RadioBrowser = hass.data[DOMAIN][CONF_RADIO_BROWSER]
        favorites = hass.data[DOMAIN][CONF_FAVORITE_RADIOS]

        idx: int = hass.data[DOMAIN][LAST_FAVORITE]

        idx = idx - 1
        idx = min(idx, len(favorites) - 1)
        idx = max(idx, 0)

        try_play_radio(radios, favorites[idx], player)
        hass.data[DOMAIN][LAST_FAVORITE] = idx

    # Register the services
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_RADIO,
        start_radio,
        schema=SERVICE_START_RADIO_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_NEXT_RADIO,
        next_radio,
        schema=SERVICE_NEXT_RADIO_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PREV_RADIO,
        prev_radio,
        schema=SERVICE_NEXT_RADIO_SCHEMA,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    del hass.data[DOMAIN]
    return True
