"""
Support for functionality to keep track of the sun.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sun/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (
    CONF_ELEVATION, CONF_MONITORED_CONDITIONS, CONF_SCAN_INTERVAL)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_utc_time, async_track_utc_time_change,
    async_track_time_interval)
from homeassistant.helpers.sun import (
    get_astral_location, get_astral_event_next, get_astral_event_date)
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'sun'

ENTITY_ID = 'sun.sun'

MIN_SCAN_INTERVAL = timedelta(minutes=1)

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
STATE_ATTR_SUNRISE = 'sunrise'
STATE_ATTR_SUNSET = 'sunset'
STATE_ATTR_DAYLIGHT = 'daylight'
STATE_ATTR_PREV_DAYLIGHT = 'prev_daylight'
STATE_ATTR_NEXT_DAYLIGHT = 'next_daylight'
DEFAULT_STATE_ATTRS = [
    STATE_ATTR_AZIMUTH, STATE_ATTR_ELEVATION, STATE_ATTR_NEXT_DAWN,
    STATE_ATTR_NEXT_DUSK, STATE_ATTR_NEXT_MIDNIGHT, STATE_ATTR_NEXT_NOON]
OPTIONAL_STATE_ATTRS = [
    STATE_ATTR_SUNRISE, STATE_ATTR_SUNSET, STATE_ATTR_DAYLIGHT,
    STATE_ATTR_PREV_DAYLIGHT, STATE_ATTR_NEXT_DAYLIGHT]
STATE_ATTRS = DEFAULT_STATE_ATTRS + OPTIONAL_STATE_ATTRS

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_MONITORED_CONDITIONS, default=DEFAULT_STATE_ATTRS):
            vol.All(cv.ensure_list, [vol.In(STATE_ATTRS)]),
        vol.Optional(CONF_SCAN_INTERVAL):
            vol.All(cv.time_period, vol.Clamp(min=MIN_SCAN_INTERVAL))
        }, extra=vol.ALLOW_EXTRA)
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Track the state of the sun."""
    if config.get(CONF_ELEVATION) is not None:
        _LOGGER.warning(
            "Elevation is now configured in home assistant core. "
            "See https://home-assistant.io/docs/configuration/basic/")

    sun = Sun(hass, get_astral_location(hass), config[DOMAIN])
    sun.point_in_time_listener(dt_util.utcnow())

    return True


class Sun(Entity):
    """Representation of the Sun."""

    entity_id = ENTITY_ID

    def __init__(self, hass, location, config):
        """Initialize the sun."""
        self.hass = hass
        self.location = location
        self._state = self.next_rising = self.next_setting = None
        self._attrs = dict.fromkeys(
            config[CONF_MONITORED_CONDITIONS], None)

        self._update_position = (
            STATE_ATTR_AZIMUTH in self._attrs or
            STATE_ATTR_ELEVATION in self._attrs)
        if self._update_position:
            scan_interval = config.get(CONF_SCAN_INTERVAL)
            if scan_interval:
                async_track_time_interval(hass, self.timer_update,
                                          scan_interval)
            else:
                # If scan_interval not specified, use old method of updating
                # once a minute on the half minute (i.e., time == xx:xx:30.)
                async_track_utc_time_change(hass, self.timer_update,
                                            second=30)

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
        attrs = {
            STATE_ATTR_NEXT_RISING: self.next_rising.isoformat(),
            STATE_ATTR_NEXT_SETTING: self.next_setting.isoformat()
        }
        for attr, func in [(STATE_ATTR_AZIMUTH, lambda x: round(x, 2)),
                           (STATE_ATTR_ELEVATION, lambda x: round(x, 2)),
                           (STATE_ATTR_NEXT_DAWN, lambda x: x.isoformat()),
                           (STATE_ATTR_NEXT_DUSK, lambda x: x.isoformat()),
                           (STATE_ATTR_NEXT_MIDNIGHT, lambda x: x.isoformat()),
                           (STATE_ATTR_NEXT_NOON, lambda x: x.isoformat()),
                           (STATE_ATTR_SUNRISE, lambda x: x.isoformat()),
                           (STATE_ATTR_SUNSET, lambda x: x.isoformat()),
                           (STATE_ATTR_DAYLIGHT, lambda x: x),
                           (STATE_ATTR_PREV_DAYLIGHT, lambda x: x),
                           (STATE_ATTR_NEXT_DAYLIGHT, lambda x: x)]:
            if attr in self._attrs:
                attrs[attr] = func(self._attrs[attr])
        return attrs

    @property
    def next_change(self):
        """Datetime when the next change to the state is."""
        # Always need to update next rising and next setting so state can be
        # determined.
        next_events = [self.next_rising, self.next_setting]
        # Only need to update remaining properties if they will be reported
        # in attributes.
        for attr in [STATE_ATTR_NEXT_DAWN,
                     STATE_ATTR_NEXT_DUSK,
                     STATE_ATTR_NEXT_MIDNIGHT,
                     STATE_ATTR_NEXT_NOON]:
            if attr in self._attrs:
                next_events.append(self._attrs[attr])
        # For sunrise, sunset and daylights, update at next "real" midnight
        # (as opposed to next_midnight, which is solar midnight.) But subtract
        # one second because point_in_time_listener() will add one.
        if any(attr in self._attrs for attr in
               [STATE_ATTR_SUNRISE, STATE_ATTR_SUNSET,
                STATE_ATTR_DAYLIGHT, STATE_ATTR_PREV_DAYLIGHT,
                STATE_ATTR_NEXT_DAYLIGHT]):
            midnight = dt_util.start_of_local_day(
                dt_util.now() + timedelta(days=1))
            next_events.append(dt_util.as_utc(midnight) - timedelta(seconds=1))
        return min(next_events)

    @callback
    def update_as_of(self, utc_point_in_time):
        """Update the attributes containing solar events."""
        # Always need to update next_rising and next_setting so state can be
        # determined.
        self.next_rising = get_astral_event_next(
            self.hass, 'sunrise', utc_point_in_time)
        self.next_setting = get_astral_event_next(
            self.hass, 'sunset', utc_point_in_time)
        # Only need to update remaining properties if they will be reported
        # in attributes.
        for attr, event, func in [
                (STATE_ATTR_NEXT_DAWN, 'dawn', get_astral_event_next),
                (STATE_ATTR_NEXT_DUSK, 'dusk', get_astral_event_next),
                (STATE_ATTR_NEXT_MIDNIGHT, 'solar_midnight',
                 get_astral_event_next),
                (STATE_ATTR_NEXT_NOON, 'solar_noon', get_astral_event_next),
                (STATE_ATTR_SUNRISE, 'sunrise', get_astral_event_date),
                (STATE_ATTR_SUNSET, 'sunset', get_astral_event_date)]:
            if attr in self._attrs:
                self._attrs[attr] = func(self.hass, event, utc_point_in_time)
        for attr, delta in [(STATE_ATTR_DAYLIGHT, 0),
                            (STATE_ATTR_PREV_DAYLIGHT, -1),
                            (STATE_ATTR_NEXT_DAYLIGHT, 1)]:
            if attr in self._attrs:
                daylight = get_astral_event_date(
                    self.hass, 'daylight',
                    utc_point_in_time + timedelta(days=delta))
                self._attrs[attr] = (daylight[1]-daylight[0]).total_seconds()

    @callback
    def update_sun_position(self, utc_point_in_time):
        """Calculate the position of the sun."""
        if STATE_ATTR_AZIMUTH in self._attrs:
            self._attrs[STATE_ATTR_AZIMUTH] = self.location.solar_azimuth(
                utc_point_in_time)
        if STATE_ATTR_ELEVATION in self._attrs:
            self._attrs[STATE_ATTR_ELEVATION] = self.location.solar_elevation(
                utc_point_in_time)

    @callback
    def point_in_time_listener(self, now):
        """Run when the state of the sun has changed."""
        if self._update_position:
            self.update_sun_position(now)
        self.update_as_of(now)
        self.async_schedule_update_ha_state()

        # Schedule next update at next_change+1 second so sun state has changed
        async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener,
            self.next_change + timedelta(seconds=1))

    @callback
    def timer_update(self, time):
        """Needed to update solar elevation and azimuth."""
        self.update_sun_position(time)
        self.async_schedule_update_ha_state()
