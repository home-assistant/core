"""
Support for functionality to keep track of the sun.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sun/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import CONF_ELEVATION
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    track_point_in_utc_time, track_utc_time_change)
from homeassistant.util import dt as dt_util
import homeassistant.helpers.config_validation as cv
import homeassistant.util as util

REQUIREMENTS = ['astral==1.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'sun'

ENTITY_ID = 'sun.sun'

STATE_ABOVE_HORIZON = 'above_horizon'
STATE_BELOW_HORIZON = 'below_horizon'

STATE_ATTR_AZIMUTH = 'azimuth'
STATE_ATTR_ELEVATION = 'elevation'
STATE_ATTR_NEXT_DAWN = 'next_dawn'
STATE_ATTR_NEXT_DUSK = 'next_dusk'
STATE_ATTR_NEXT_MIDNIGHT = 'next_midnight'
STATE_ATTR_NEXT_NOON = 'next_noon'
STATE_ATTR_NEXT_RISING = 'next_rising'
STATE_ATTR_NEXT_SETTING = 'next_setting'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_ELEVATION): cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)


def is_on(hass, entity_id=None):
    """Test if the sun is currently up based on the statemachine."""
    entity_id = entity_id or ENTITY_ID

    return hass.states.is_state(entity_id, STATE_ABOVE_HORIZON)


def next_dawn(hass, entity_id=None):
    """Local datetime object of the next dawn.

    Async friendly.
    """
    utc_next = next_dawn_utc(hass, entity_id)

    return dt_util.as_local(utc_next) if utc_next else None


def next_dawn_utc(hass, entity_id=None):
    """UTC datetime object of the next dawn.

    Async friendly.
    """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return dt_util.parse_datetime(
            state.attributes[STATE_ATTR_NEXT_DAWN])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_DAWN does not exist
        return None


def next_dusk(hass, entity_id=None):
    """Local datetime object of the next dusk.

    Async friendly.
    """
    utc_next = next_dusk_utc(hass, entity_id)

    return dt_util.as_local(utc_next) if utc_next else None


def next_dusk_utc(hass, entity_id=None):
    """UTC datetime object of the next dusk.

    Async friendly.
    """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return dt_util.parse_datetime(
            state.attributes[STATE_ATTR_NEXT_DUSK])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_DUSK does not exist
        return None


def next_midnight(hass, entity_id=None):
    """Local datetime object of the next midnight.

    Async friendly.
    """
    utc_next = next_midnight_utc(hass, entity_id)

    return dt_util.as_local(utc_next) if utc_next else None


def next_midnight_utc(hass, entity_id=None):
    """UTC datetime object of the next midnight.

    Async friendly.
    """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return dt_util.parse_datetime(
            state.attributes[STATE_ATTR_NEXT_MIDNIGHT])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_MIDNIGHT does not exist
        return None


def next_noon(hass, entity_id=None):
    """Local datetime object of the next solar noon.

    Async friendly.
    """
    utc_next = next_noon_utc(hass, entity_id)

    return dt_util.as_local(utc_next) if utc_next else None


def next_noon_utc(hass, entity_id=None):
    """UTC datetime object of the next noon.

    Async friendly.
    """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return dt_util.parse_datetime(
            state.attributes[STATE_ATTR_NEXT_NOON])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_NOON does not exist
        return None


def next_setting(hass, entity_id=None):
    """Local datetime object of the next sun setting.

    Async friendly.
    """
    utc_next = next_setting_utc(hass, entity_id)

    return dt_util.as_local(utc_next) if utc_next else None


def next_setting_utc(hass, entity_id=None):
    """UTC datetime object of the next sun setting.

    Async friendly.
    """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return dt_util.parse_datetime(
            state.attributes[STATE_ATTR_NEXT_SETTING])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_SETTING does not exist
        return None


def next_rising(hass, entity_id=None):
    """Local datetime object of the next sun rising.

    Async friendly.
    """
    utc_next = next_rising_utc(hass, entity_id)

    return dt_util.as_local(utc_next) if utc_next else None


def next_rising_utc(hass, entity_id=None):
    """UTC datetime object of the next sun rising.

    Async friendly.
    """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return dt_util.parse_datetime(state.attributes[STATE_ATTR_NEXT_RISING])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_RISING does not exist
        return None


def setup(hass, config):
    """Track the state of the sun."""
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    latitude = util.convert(hass.config.latitude, float)
    longitude = util.convert(hass.config.longitude, float)
    errors = []

    if latitude is None:
        errors.append('Latitude needs to be a decimal value')
    elif -90 > latitude < 90:
        errors.append('Latitude needs to be -90 .. 90')

    if longitude is None:
        errors.append('Longitude needs to be a decimal value')
    elif -180 > longitude < 180:
        errors.append('Longitude needs to be -180 .. 180')

    if errors:
        _LOGGER.error('Invalid configuration received: %s', ", ".join(errors))
        return False

    platform_config = config.get(DOMAIN, {})

    elevation = platform_config.get(CONF_ELEVATION)
    if elevation is None:
        elevation = hass.config.elevation or 0

    from astral import Location

    location = Location(('', '', latitude, longitude,
                         hass.config.time_zone.zone, elevation))

    sun = Sun(hass, location)
    sun.point_in_time_listener(dt_util.utcnow())

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
        self.solar_elevation = self.solar_azimuth = 0

        track_utc_time_change(hass, self.timer_update, second=30)

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
            STATE_ATTR_ELEVATION: round(self.solar_elevation, 2),
            STATE_ATTR_AZIMUTH: round(self.solar_azimuth, 2)
        }

    @property
    def next_change(self):
        """Datetime when the next change to the state is."""
        return min(self.next_dawn, self.next_dusk, self.next_midnight,
                   self.next_noon, self.next_rising, self.next_setting)

    @staticmethod
    def get_next_solar_event(callable_on_astral_location,
                             utc_point_in_time, mod, increment):
        """Calculate sun state at a point in UTC time."""
        import astral

        while True:
            try:
                next_dt = callable_on_astral_location(
                    utc_point_in_time + timedelta(days=mod), local=False)
                if next_dt > utc_point_in_time:
                    break
            except astral.AstralError:
                pass
            mod += increment

        return next_dt

    def update_as_of(self, utc_point_in_time):
        """Update the attributes containing solar events."""
        self.next_dawn = Sun.get_next_solar_event(
            self.location.dawn, utc_point_in_time, -1, 1)
        self.next_dusk = Sun.get_next_solar_event(
            self.location.dusk, utc_point_in_time, -1, 1)
        self.next_midnight = Sun.get_next_solar_event(
            self.location.solar_midnight, utc_point_in_time, -1, 1)
        self.next_noon = Sun.get_next_solar_event(
            self.location.solar_noon, utc_point_in_time, -1, 1)
        self.next_rising = Sun.get_next_solar_event(
            self.location.sunrise, utc_point_in_time, -1, 1)
        self.next_setting = Sun.get_next_solar_event(
            self.location.sunset, utc_point_in_time, -1, 1)

    def update_sun_position(self, utc_point_in_time):
        """Calculate the position of the sun."""
        from astral import Astral

        self.solar_azimuth = Astral().solar_azimuth(
            utc_point_in_time,
            self.location.latitude,
            self.location.longitude)

        self.solar_elevation = Astral().solar_elevation(
            utc_point_in_time,
            self.location.latitude,
            self.location.longitude)

    def point_in_time_listener(self, now):
        """Run when the state of the sun has changed."""
        self.update_as_of(now)
        self.schedule_update_ha_state()

        # Schedule next update at next_change+1 second so sun state has changed
        track_point_in_utc_time(
            self.hass, self.point_in_time_listener,
            self.next_change + timedelta(seconds=1))

    def timer_update(self, time):
        """Needed to update solar elevation and azimuth."""
        self.update_sun_position(time)
        self.schedule_update_ha_state()
