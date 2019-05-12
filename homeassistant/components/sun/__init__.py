"""Support for functionality to keep track of the sun."""
import logging
from datetime import timedelta

from homeassistant.const import (
    CONF_ELEVATION, SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.sun import (
    get_astral_location, get_location_astral_event_next)
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'sun'

ENTITY_ID = 'sun.sun'

STATE_ABOVE_HORIZON = 'above_horizon'
STATE_BELOW_HORIZON = 'below_horizon'

STATE_ATTR_AZIMUTH = 'azimuth'
STATE_ATTR_ELEVATION = 'elevation'
STATE_ATTR_RISING = 'rising'
STATE_ATTR_NEXT_DAWN = 'next_dawn'
STATE_ATTR_NEXT_DUSK = 'next_dusk'
STATE_ATTR_NEXT_MIDNIGHT = 'next_midnight'
STATE_ATTR_NEXT_NOON = 'next_noon'
STATE_ATTR_NEXT_RISING = 'next_rising'
STATE_ATTR_NEXT_SETTING = 'next_setting'
STATE_ATTR_PHASE = 'phase'

PHASE_NIGHT = 'night'
PHASE_ASTRONOMICAL_TWILIGHT = 'astronomical_twilight'
PHASE_NAUTICAL_TWILIGHT = 'nautical_twilight'
PHASE_TWILIGHT = 'twilight'
PHASE_SMALL_DAY = 'small_day'
PHASE_DAY = 'day'

# 4 mins is one degree of arc change of the sun on its circle.
# During the night and the middle of the day we don't update
# that much since it's not important.
_PHASE_UPDATES = {
    PHASE_NIGHT: timedelta(minutes=4*5),
    PHASE_ASTRONOMICAL_TWILIGHT: timedelta(minutes=4*2),
    PHASE_NAUTICAL_TWILIGHT: timedelta(minutes=4*2),
    PHASE_TWILIGHT: timedelta(minutes=4),
    PHASE_SMALL_DAY: timedelta(minutes=2),
    PHASE_DAY: timedelta(minutes=4),
}


async def async_setup(hass, config):
    """Track the state of the sun."""
    if config.get(CONF_ELEVATION) is not None:
        _LOGGER.warning(
            "Elevation is now configured in home assistant core. "
            "See https://home-assistant.io/docs/configuration/basic/")
    Sun(hass, get_astral_location(hass))
    return True


class Sun(Entity):
    """Representation of the Sun."""

    entity_id = ENTITY_ID

    def __init__(self, hass, location):
        """Initialize the sun."""
        self.hass = hass
        self.location = location
        self._state = self.next_rising = self.next_setting = None
        self.next_dawn = self.next_dusk = None
        self.next_midnight = self.next_noon = None
        self.solar_elevation = self.solar_azimuth = None
        self.rising = self.phase = None

        self._next_change = None
        self.update_events(dt_util.utcnow())

    @property
    def name(self):
        """Return the name."""
        return "Sun"

    @property
    def state(self):
        """Return the state of the sun."""
        if self.next_rising > self.next_setting:
            return STATE_ABOVE_HORIZON

        return STATE_BELOW_HORIZON

    @property
    def state_attributes(self):
        """Return the state attributes of the sun."""
        return {
            STATE_ATTR_NEXT_DAWN: self.next_dawn.isoformat(),
            STATE_ATTR_NEXT_DUSK: self.next_dusk.isoformat(),
            STATE_ATTR_NEXT_MIDNIGHT: self.next_midnight.isoformat(),
            STATE_ATTR_NEXT_NOON: self.next_noon.isoformat(),
            STATE_ATTR_NEXT_RISING: self.next_rising.isoformat(),
            STATE_ATTR_NEXT_SETTING: self.next_setting.isoformat(),
            STATE_ATTR_ELEVATION: self.solar_elevation,
            STATE_ATTR_AZIMUTH: self.solar_azimuth,
            STATE_ATTR_RISING: self.rising,
        }

    def _check_event(self, utc_point_in_time, event, before):
        next_utc = get_location_astral_event_next(
            self.location, event, utc_point_in_time)
        if next_utc < self._next_change:
            self._next_change = next_utc
            self.phase = before
        return next_utc

    @callback
    def update_events(self, utc_point_in_time):
        """Update the attributes containing solar events."""
        self._next_change = utc_point_in_time + timedelta(days=400)

        self.location.solar_depression = 'astronomical'
        self._check_event(utc_point_in_time, 'dawn', PHASE_NIGHT)
        self.location.solar_depression = 'nautical'
        self._check_event(
            utc_point_in_time, 'dawn', PHASE_ASTRONOMICAL_TWILIGHT)
        self.location.solar_depression = 'civil'
        self.next_dawn = self._check_event(
            utc_point_in_time, 'dawn', PHASE_NAUTICAL_TWILIGHT)
        self.next_rising = self._check_event(
            utc_point_in_time, SUN_EVENT_SUNRISE, PHASE_TWILIGHT)
        self.location.solar_depression = -10
        self._check_event(utc_point_in_time, 'dawn', PHASE_SMALL_DAY)
        self.next_noon = self._check_event(
            utc_point_in_time, 'solar_noon', None)
        self._check_event(utc_point_in_time, 'dusk', PHASE_DAY)
        self.next_setting = self._check_event(
            utc_point_in_time, SUN_EVENT_SUNSET, PHASE_SMALL_DAY)
        self.location.solar_depression = 'civil'
        self.next_dusk = self._check_event(
            utc_point_in_time, 'dusk', PHASE_TWILIGHT)
        self.location.solar_depression = 'nautical'
        self._check_event(
            utc_point_in_time, 'dusk', PHASE_NAUTICAL_TWILIGHT)
        self.location.solar_depression = 'astronomical'
        self._check_event(
            utc_point_in_time, 'dusk', PHASE_ASTRONOMICAL_TWILIGHT)
        self.next_midnight = self._check_event(
            utc_point_in_time, 'solar_midnight', None)

        # Need to calculate phase if next is noon or midnight
        if self.phase is None:
            elevation = self.location.solar_elevation(self._next_change)
            if elevation >= 10:
                self.phase = PHASE_DAY
            elif elevation >= 0:
                self.phase = PHASE_SMALL_DAY
            elif elevation >= -6:
                self.phase = PHASE_TWILIGHT
            elif elevation >= -12:
                self.phase = PHASE_NAUTICAL_TWILIGHT
            elif elevation >= -18:
                self.phase = PHASE_ASTRONOMICAL_TWILIGHT
            else:
                self.phase = PHASE_NIGHT

        self.rising = self.next_noon < self.next_midnight

        _LOGGER.info(
            "sun phase_update@%s: phase=%s",
            utc_point_in_time.isoformat(),
            self.phase,
        )
        self.update_sun_position(utc_point_in_time)

        # Set timer for the next solar event
        async_track_point_in_utc_time(
            self.hass, self.update_events,
            self._next_change)
        _LOGGER.debug("next time: %s", self._next_change)

    @callback
    def update_sun_position(self, utc_point_in_time):
        """Calculate the position of the sun."""
        # Round azimuth to nearest 0.5
        self.solar_azimuth = round(
            self.location.solar_azimuth(utc_point_in_time), 2)
        self.solar_elevation = round(
            self.location.solar_elevation(utc_point_in_time), 2)

        _LOGGER.info(
            "sun position_update@%s: elevation=%s azimuth=%s",
            utc_point_in_time.isoformat(),
            self.solar_elevation, self.solar_azimuth
        )
        self.async_write_ha_state()

        next_update = utc_point_in_time + _PHASE_UPDATES[self.phase]
        # if the next update is within 30 seconds of a change
        # the next change will pick it up.
        if next_update + timedelta(seconds=30) > self._next_change:
            return
        async_track_point_in_utc_time(
            self.hass, self.update_sun_position,
            next_update)
