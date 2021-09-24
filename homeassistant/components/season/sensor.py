"""Support for tracking which astronomical or meteorological season it is."""
from datetime import datetime
import logging

import ephem
import voluptuous as vol

from homeassistant import util
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.helpers import config_validation as cv
from homeassistant.util.dt import utcnow

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

ATTR_DAYS_LEFT = "days_left"
ATTR_DAYS_IN = "days_in"
ATTR_NEXT_SEASON_UTC = "next_season_utc"

VALID_TYPES = [
    TYPE_ASTRONOMICAL,
    TYPE_METEOROLOGICAL,
]
 
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
    add_entities([Season(hass, hemisphere, _type, name)], True)

    return True


def get_season(self):
    """Calculate the current season."""

    date = self.datetime
    hemisphere = self.hemisphere
    season_tracking_type = self.type

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

    if hemisphere == EQUATOR:
        season = None
        days_left = None
        days_in = None
        next_date = None
    elif date < spring_start or date >= winter_start:
        season = STATE_WINTER
        if date.month >= 12:
            spring_start = ephem.next_equinox(str(date.year + 1)).datetime()
        else:
            winter_start = ephem.next_solstice(
                summer_start.replace(year=date.year - 1)
            ).datetime()
        days_left = spring_start.date() - date.date()
        days_in = date.date() - winter_start.date()
        next_date = spring_start
    elif date < summer_start:
        season = STATE_SPRING
        days_left = summer_start.date() - date.date()
        days_in = date.date() - spring_start.date()
        next_date = summer_start
    elif date < autumn_start:
        season = STATE_SUMMER
        days_left = autumn_start.date() - date.date()
        days_in = date.date() - summer_start.date()
        next_date = autumn_start
    elif date < winter_start:
        season = STATE_AUTUMN
        days_left = winter_start.date() - date.date()
        days_in = date.date() - autumn_start.date()
        next_date = winter_start

    # If user is located in the southern hemisphere swap the season
    if hemisphere == SOUTHERN:
        season = HEMISPHERE_SEASON_SWAP.get(season)

    self.season = season
    if hemisphere == EQUATOR:
        self.days_left = days_left
        self.days_in = days_in
        self.next_date = next_date
    else:
        self.days_left = days_left.days
        self.days_in = abs(days_in.days) + 1
        self.next_date = next_date.strftime("%Y %b %d %H:%M:%S")


class Season(SensorEntity):
    """Representation of the current season."""

    def __init__(self, hass, hemisphere, season_tracking_type, name):
        """Initialize the season."""
        self.hass = hass
        self._name = name
        self.hemisphere = hemisphere
        self.datetime = None
        self.type = season_tracking_type
        self.season = None
        self.days_left = None
        self.days_in = None
        self.next_date = None

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def native_value(self):
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

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        if self.hemisphere != EQUATOR:
            attr[ATTR_DAYS_LEFT] = self.days_left
            attr[ATTR_DAYS_IN] = self.days_in
            attr[ATTR_NEXT_SEASON_UTC] = self.next_date
        return attr

    def update(self):
        """Update season."""
        self.datetime = utcnow().replace(tzinfo=None)
        get_season(self)
