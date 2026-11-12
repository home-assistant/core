"""Services for the Ombi integration."""

from enum import StrEnum

import probatio
import pyombi

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_SEASON, DOMAIN


class OmbiService(StrEnum):
    """Store keys for Ombi services."""

    SUBMIT_MOVIE_REQUEST = "submit_movie_request"
    SUBMIT_TV_REQUEST = "submit_tv_request"
    SUBMIT_MUSIC_REQUEST = "submit_music_request"


class OmbiServiceArgument(StrEnum):
    """Store keys for Ombi service arguments."""

    NAME = "name"
    SEASON = "season"


SUBMIT_MOVIE_REQUEST_SERVICE_SCHEMA = probatio.Schema(
    {probatio.Required(OmbiServiceArgument.NAME): cv.string}
)

SUBMIT_MUSIC_REQUEST_SERVICE_SCHEMA = probatio.Schema(
    {probatio.Required(OmbiServiceArgument.NAME): cv.string}
)

SUBMIT_TV_REQUEST_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(OmbiServiceArgument.NAME): cv.string,
        probatio.Optional(
            OmbiServiceArgument.SEASON, default=DEFAULT_SEASON
        ): probatio.In(["first", "latest", "all"]),
    }
)


def _submit_movie_request(call: ServiceCall) -> None:
    """Submit request for movie."""
    ombi: pyombi.Ombi = call.hass.data[DOMAIN]["instance"]
    name = call.data[OmbiServiceArgument.NAME]
    movies = ombi.search_movie(name)
    if movies:
        movie = movies[0]
        ombi.request_movie(movie["theMovieDbId"])
    else:
        raise Warning("No movie found.")


def _submit_tv_request(call: ServiceCall) -> None:
    """Submit request for TV show."""
    ombi: pyombi.Ombi = call.hass.data[DOMAIN]["instance"]
    name = call.data[OmbiServiceArgument.NAME]
    tv_shows = ombi.search_tv(name)

    if tv_shows:
        season = call.data[OmbiServiceArgument.SEASON]
        show = tv_shows[0]["id"]
        if season == "first":
            ombi.request_tv(show, request_first=True)
        elif season == "latest":
            ombi.request_tv(show, request_latest=True)
        elif season == "all":
            ombi.request_tv(show, request_all=True)
    else:
        raise Warning("No TV show found.")


def _submit_music_request(call: ServiceCall) -> None:
    """Submit request for music album."""
    ombi: pyombi.Ombi = call.hass.data[DOMAIN]["instance"]
    name = call.data[OmbiServiceArgument.NAME]
    music = ombi.search_music_album(name)
    if music:
        ombi.request_music(music[0]["foreignAlbumId"])
    else:
        raise Warning("No music album found.")


def setup_services(hass: HomeAssistant) -> None:
    """Register the Ombi services."""
    hass.services.register(
        DOMAIN,
        OmbiService.SUBMIT_MOVIE_REQUEST,
        _submit_movie_request,
        schema=SUBMIT_MOVIE_REQUEST_SERVICE_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        OmbiService.SUBMIT_MUSIC_REQUEST,
        _submit_music_request,
        schema=SUBMIT_MUSIC_REQUEST_SERVICE_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        OmbiService.SUBMIT_TV_REQUEST,
        _submit_tv_request,
        schema=SUBMIT_TV_REQUEST_SERVICE_SCHEMA,
    )
