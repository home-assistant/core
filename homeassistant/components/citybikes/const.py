"""Constants for the CityBikes component."""

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_RADIUS
from homeassistant.helpers import config_validation as cv

DOMAIN = "citybikes"

CONF_NETWORK = "network"
CONF_STATIONS_LIST = "stations"
CONF_STATION_FILTER = "station_filter"

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RADIUS, CONF_STATIONS_LIST),
    SENSOR_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME, default=""): cv.string,
            vol.Optional(CONF_NETWORK): cv.string,
            vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
            vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
            vol.Optional(CONF_RADIUS, "station_filter"): cv.positive_int,
            vol.Optional(CONF_STATIONS_LIST, "station_filter"): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
        }
    ),
)
