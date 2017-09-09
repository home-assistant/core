"""
Support for functionality to keep track of the sun.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sun/
"""
import asyncio
import logging
from datetime import timedelta

from homeassistant.const import CONF_ELEVATION
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_utc_time, async_track_utc_time_change)
from homeassistant.helpers.sun import (
    get_astral_location, get_astral_event_next)
from homeassistant.util import dt as dt_util

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


@asyncio.coroutine
def async_setup(hass, config):
    """Track the state of the sun."""
    if config.get(CONF_ELEVATION) is not None:
        _LOGGER.warning(
            "Elevation is now configured in home assistant core. "
            "See https://home-assistant.io/docs/configuration/basic/")

    sun = Sun(hass, get_astral_location(hass))
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
        self.solar_elevation = self.solar_azimuth = None

        async_track_utc_time_change(hass, self.timer_update, second=30)

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

    @callback
    def update_as_of(self, utc_point_in_time):
        """Update the attributes containing solar events."""
        self.next_dawn = get_astral_event_next(
            self.hass, 'dawn', utc_point_in_time)
        self.next_dusk = get_astral_event_next(
            self.hass, 'dusk', utc_point_in_time)
        self.next_midnight = get_astral_event_next(
            self.hass, 'solar_midnight', utc_point_in_time)
        self.next_noon = get_astral_event_next(
            self.hass, 'solar_noon', utc_point_in_time)
        self.next_rising = get_astral_event_next(
            self.hass, 'sunrise', utc_point_in_time)
        self.next_setting = get_astral_event_next(
            self.hass, 'sunset', utc_point_in_time)

    @callback
    def update_sun_position(self, utc_point_in_time):
        """Calculate the position of the sun."""
        self.solar_azimuth = self.location.solar_azimuth(utc_point_in_time)
        self.solar_elevation = self.location.solar_elevation(utc_point_in_time)

    @callback
    def point_in_time_listener(self, now):
        """Run when the state of the sun has changed."""
        self.update_sun_position(now)
        self.update_as_of(now)
        self.hass.async_add_job(self.async_update_ha_state())

        # Schedule next update at next_change+1 second so sun state has changed
        async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener,
            self.next_change + timedelta(seconds=1))

    @callback
    def timer_update(self, time):
        """Needed to update solar elevation and azimuth."""
        self.update_sun_position(time)
        self.hass.async_add_job(self.async_update_ha_state())
