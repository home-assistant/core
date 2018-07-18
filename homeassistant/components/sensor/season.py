"""
Support for tracking which astronomical or meteorological season it is.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/season/
"""
import logging
from datetime import datetime

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_TYPE
from homeassistant.helpers.entity import Entity
from homeassistant import util

REQUIREMENTS = ['ephem==3.7.6.0']

_LOGGER = logging.getLogger(__name__)

NORTHERN = 'northern'
SOUTHERN = 'southern'
EQUATOR = 'equator'
STATE_SPRING = 'spring'
STATE_SUMMER = 'summer'
STATE_AUTUMN = 'autumn'
STATE_WINTER = 'winter'
TYPE_ASTRONOMICAL = 'astronomical'
TYPE_METEOROLOGICAL = 'meteorological'
VALID_TYPES = [TYPE_ASTRONOMICAL, TYPE_METEOROLOGICAL]

HEMISPHERE_SEASON_SWAP = {STATE_WINTER: STATE_SUMMER,
                          STATE_SPRING: STATE_AUTUMN,
                          STATE_AUTUMN: STATE_SPRING,
                          STATE_SUMMER: STATE_WINTER}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_TYPE, default=TYPE_ASTRONOMICAL): vol.In(VALID_TYPES)
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Display the current season."""
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    latitude = util.convert(hass.config.latitude, float)
    _type = config.get(CONF_TYPE)

    if latitude < 0:
        hemisphere = SOUTHERN
    elif latitude > 0:
        hemisphere = NORTHERN
    else:
        hemisphere = EQUATOR

    _LOGGER.debug(_type)
    add_devices([Season(hass, hemisphere, _type)])

    return True


def get_season(date, hemisphere, season_tracking_type):
    """Calculate the current season."""
    import ephem

    if hemisphere == 'equator':
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

    def __init__(self, hass, hemisphere, season_tracking_type):
        """Initialize the season."""
        self.hass = hass
        self.hemisphere = hemisphere
        self.datetime = datetime.now()
        self.type = season_tracking_type
        self.season = get_season(self.datetime, self.hemisphere, self.type)

    @property
    def name(self):
        """Return the name."""
        return "Season"

    @property
    def state(self):
        """Return the current season."""
        return self.season

    def update(self):
        """Update season."""
        self.datetime = datetime.now()
        self.season = get_season(self.datetime, self.hemisphere, self.type)
