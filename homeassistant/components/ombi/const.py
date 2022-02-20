"""Support for Ombi."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntityDescription

ATTR_SEASON = "season"

CONF_URLBASE = "urlbase"

DEFAULT_NAME = DOMAIN = "ombi"
DEFAULT_PORT = 5000
DEFAULT_SEASON = "latest"
DEFAULT_SSL = False
DEFAULT_URLBASE = ""

SERVICE_MOVIE_REQUEST = "submit_movie_request"
SERVICE_MUSIC_REQUEST = "submit_music_request"
SERVICE_TV_REQUEST = "submit_tv_request"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="movies",
        name="Movie requests",
        icon="mdi:movie",
    ),
    SensorEntityDescription(
        key="tv",
        name="TV show requests",
        icon="mdi:television-classic",
    ),
    SensorEntityDescription(
        key="music",
        name="Music album requests",
        icon="mdi:album",
    ),
    SensorEntityDescription(
        key="pending",
        name="Pending requests",
        icon="mdi:clock-alert-outline",
    ),
    SensorEntityDescription(
        key="approved",
        name="Approved requests",
        icon="mdi:check",
    ),
    SensorEntityDescription(
        key="available",
        name="Available requests",
        icon="mdi:download",
    ),
)
