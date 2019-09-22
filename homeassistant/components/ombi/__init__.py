"""Support for Ombi."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv

from .const import CONF_URLBASE, DEFAULT_PORT, DEFAULT_SSL, DEFAULT_URLBASE, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_URLBASE, default=DEFAULT_URLBASE): cv.string,
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCAN_INTERVAL = timedelta(seconds=60)


def setup(hass, config):
    """Set up the Ombi component platform."""
    import pyombi

    urlbase = f"{config[DOMAIN][CONF_URLBASE].strip('/') if config[DOMAIN][CONF_URLBASE] else ''}/"

    ombi = pyombi.Ombi(
        ssl=config[DOMAIN][CONF_SSL],
        host=config[DOMAIN][CONF_HOST],
        port=config[DOMAIN][CONF_PORT],
        api_key=config[DOMAIN][CONF_API_KEY],
        username=config[DOMAIN][CONF_USERNAME],
        urlbase=urlbase,
    )

    try:
        ombi.test_connection()
    except pyombi.OmbiError as err:
        _LOGGER.warning("Unable to setup Ombi: %s", err)
        return

    hass.data[DOMAIN] = {"instance": ombi}

    def submit_movie_request(call):
        """Submit request for movie."""
        name = call.data.get("name")
        movies = ombi.search_movie(name)
        if movies:
            ombi.request_movie(movies[0]["theMovieDbId"])

    def submit_tv_request(call):
        """Submit request for TV show."""
        name = call.data.get("name")
        tv_shows = ombi.search_tv(name)

        if tv_shows:
            season = call.data.get("season")
            show = tv_shows[0]["id"]
            if season == "first":
                ombi.request_tv(show, request_first=True)
            elif season == "latest":
                ombi.request_tv(show, request_latest=True)
            elif season == "all":
                ombi.request_tv(show, request_all=True)

    def submit_music_request(call):
        """Submit request for music album."""
        name = call.data.get("name")
        music = ombi.search_music_album(name)
        if music:
            ombi.request_music(music[0]["foreignAlbumId"])

    hass.services.register(DOMAIN, "submit_movie_request", submit_movie_request)
    hass.services.register(DOMAIN, "submit_tv_request", submit_tv_request)
    hass.services.register(DOMAIN, "submit_music_request", submit_music_request)
    hass.helpers.discovery.load_platform("sensor", DOMAIN, {}, config)

    return True
