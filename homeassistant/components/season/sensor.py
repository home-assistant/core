"""Support for tracking which astronomical or meteorological season it is."""
from datetime import datetime
import logging

import ephem
import voluptuous as vol

from homeassistant import util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_TYPE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Season"

EQUATOR = "equator"

NORTHERN = "northern"

SOUTHERN = "southern"
STATE_AUTUMN = "autumn"
STATE_SPRING = "spring"
STATE_SUMMER = "summer"
STATE_WINTER = "winter"

TYPE_ASTRONOMICAL = "astronomical"
TYPE_METEOROLOGICAL = "meteorological"

VALID_TYPES = [TYPE_ASTRONOMICAL, TYPE_METEOROLOGICAL]

HEMISPHERE_SEASON_SWAP = {
    STATE_WINTER: STATE_SUMMER,
    STATE_SPRING: STATE_AUTUMN,
    STATE_AUTUMN: STATE_SPRING,
    STATE_SUMMER: STATE_WINTER,
}

SEASON_ICONS = {
    STATE_SPRING: "mdi:flower",
    STATE_SUMMER: "mdi:sunglasses",
    STATE_AUTUMN: "mdi:leaf",
    STATE_WINTER: "mdi:snowflake",
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_TYPE, default=TYPE_ASTRONOMICAL): vol.In(VALID_TYPES),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Display the current season."""
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    latitude = util.convert(hass.config.latitude, float)
    _type = config.get(CONF_TYPE)
    name = config.get(CONF_NAME)

    if latitude < 0:
        hemisphere = SOUTHERN
    elif latitude > 0:
        hemisphere = NORTHERN
    else:
        hemisphere = EQUATOR

    _LOGGER.debug(_type)
    add_entities([Season(hass, hemisphere, _type, name)])

    return True


def get_season(date, hemisphere, season_tracking_type):
    """Calculate the current season."""

    if hemisphere == "equator":
        return None

    if season_tracking_type == TYPE_ASTRONOMICAL:
        spring_start = ephem.next_equinox(str(date.year)).datetime()
        summer_start = ephem.next_solstice(str(date.year)).datetime()
        autumn_start = ephem.next_equinox(spring_start).datetime()
        winter_start = ephem.next_solstice(summer_start).datetime()
    else:
        spring_start = datetime(2017, 3, 1).replace(year=date.year)
        summer_start = spring_start.replace(month=6)
        autumn_start = spring_start.replace(month=9)
        winter_start = spring_start.replace(month=12)

    if spring_start <= date < summer_start:
        season = STATE_SPRING
    elif summer_start <= date < autumn_start:
        season = STATE_SUMMER
    elif autumn_start <= date < winter_start:
        season = STATE_AUTUMN
    elif winter_start <= date or spring_start > date:
        season = STATE_WINTER

    # If user is located in the southern hemisphere swap the season
    if hemisphere == NORTHERN:
        return season
    return HEMISPHERE_SEASON_SWAP.get(season)


class Season(Entity):
    """Representation of the current season."""

    def __init__(self, hass, hemisphere, season_tracking_type, name):
        """Initialize the season."""
        self.hass = hass
        self._name = name
        self.hemisphere = hemisphere
        self.datetime = dt_util.utcnow().replace(tzinfo=None)
        self.type = season_tracking_type
        self.season = get_season(self.datetime, self.hemisphere, self.type)

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the current season."""
        return self.season

    @property
    def device_class(self):
        """Return the device class."""
        return "season__season"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SEASON_ICONS.get(self.season, "mdi:cloud")

    def update(self):
        """Update season."""
        self.datetime = dt_util.utcnow().replace(tzinfo=None)
        self.season = get_season(self.datetime, self.hemisphere, self.type)
