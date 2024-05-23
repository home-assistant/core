"""Support for Ombi."""

import logging

import pyombi
import voluptuous as vol

from homeassistant.const import (
    ATTR_NAME,
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_SEASON,
    CONF_URLBASE,
    DEFAULT_PORT,
    DEFAULT_SEASON,
    DEFAULT_SSL,
    DEFAULT_URLBASE,
    DOMAIN,
    SERVICE_MOVIE_REQUEST,
    SERVICE_MUSIC_REQUEST,
    SERVICE_TV_REQUEST,
)

_LOGGER = logging.getLogger(__name__)


def urlbase(value) -> str:
    """Validate and transform urlbase."""
    if value is None:
        raise vol.Invalid("string value is None")
    value = str(value).strip("/")
    if not value:
        return value
    return f"{value}/"


SUBMIT_MOVIE_REQUEST_SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_NAME): cv.string})

SUBMIT_MUSIC_REQUEST_SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_NAME): cv.string})

SUBMIT_TV_REQUEST_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Optional(ATTR_SEASON, default=DEFAULT_SEASON): vol.In(
            ["first", "latest", "all"]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Exclusive(CONF_API_KEY, "auth"): cv.string,
                vol.Exclusive(CONF_PASSWORD, "auth"): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_URLBASE, default=DEFAULT_URLBASE): urlbase,
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            },
            cv.has_at_least_one_key("auth"),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ombi component platform."""

    ombi = pyombi.Ombi(
        ssl=config[DOMAIN][CONF_SSL],
        host=config[DOMAIN][CONF_HOST],
        port=config[DOMAIN][CONF_PORT],
        urlbase=config[DOMAIN][CONF_URLBASE],
        username=config[DOMAIN][CONF_USERNAME],
        password=config[DOMAIN].get(CONF_PASSWORD),
        api_key=config[DOMAIN].get(CONF_API_KEY),
    )

    try:
        ombi.authenticate()
        ombi.test_connection()
    except pyombi.OmbiError as err:
        _LOGGER.warning("Unable to setup Ombi: %s", err)
        return False

    hass.data[DOMAIN] = {"instance": ombi}

    def submit_movie_request(call: ServiceCall) -> None:
        """Submit request for movie."""
        name = call.data[ATTR_NAME]
        movies = ombi.search_movie(name)
        if movies:
            movie = movies[0]
            ombi.request_movie(movie["theMovieDbId"])
        else:
            raise Warning("No movie found.")

    def submit_tv_request(call: ServiceCall) -> None:
        """Submit request for TV show."""
        name = call.data[ATTR_NAME]
        tv_shows = ombi.search_tv(name)

        if tv_shows:
            season = call.data[ATTR_SEASON]
            show = tv_shows[0]["id"]
            if season == "first":
                ombi.request_tv(show, request_first=True)
            elif season == "latest":
                ombi.request_tv(show, request_latest=True)
            elif season == "all":
                ombi.request_tv(show, request_all=True)
        else:
            raise Warning("No TV show found.")

    def submit_music_request(call: ServiceCall) -> None:
        """Submit request for music album."""
        name = call.data[ATTR_NAME]
        music = ombi.search_music_album(name)
        if music:
            ombi.request_music(music[0]["foreignAlbumId"])
        else:
            raise Warning("No music album found.")

    hass.services.register(
        DOMAIN,
        SERVICE_MOVIE_REQUEST,
        submit_movie_request,
        schema=SUBMIT_MOVIE_REQUEST_SERVICE_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_MUSIC_REQUEST,
        submit_music_request,
        schema=SUBMIT_MUSIC_REQUEST_SERVICE_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_TV_REQUEST,
        submit_tv_request,
        schema=SUBMIT_TV_REQUEST_SERVICE_SCHEMA,
    )
    load_platform(hass, Platform.SENSOR, DOMAIN, {}, config)

    return True
