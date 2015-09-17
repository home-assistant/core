"""
homeassistant.components.sun
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to keep track of the sun.

Event listener
--------------
The suns event listener will call the service when the sun rises or sets with
an offset.

The sun event need to have the type 'sun', which service to call, which event
(sunset or sunrise) and the offset.

{
    "type": "sun",
    "service": "switch.turn_on",
    "event": "sunset",
    "offset": "-01:00:00"
}
"""
import logging
from datetime import timedelta
import urllib

import homeassistant.util as util
import homeassistant.util.dt as dt_util
from homeassistant.helpers.event import (
    track_point_in_utc_time, track_point_in_time)
from homeassistant.helpers.entity import Entity
from homeassistant.components.scheduler import ServiceEventListener

DEPENDENCIES = []
REQUIREMENTS = ['astral==0.8.1']
DOMAIN = "sun"
ENTITY_ID = "sun.sun"

CONF_ELEVATION = 'elevation'

STATE_ABOVE_HORIZON = "above_horizon"
STATE_BELOW_HORIZON = "below_horizon"

STATE_ATTR_NEXT_RISING = "next_rising"
STATE_ATTR_NEXT_SETTING = "next_setting"

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """ Returns if the sun is currently up based on the statemachine. """
    entity_id = entity_id or ENTITY_ID

    return hass.states.is_state(entity_id, STATE_ABOVE_HORIZON)


def next_setting(hass, entity_id=None):
    """ Returns the local datetime object of the next sun setting. """
    utc_next = next_setting_utc(hass, entity_id)

    return dt_util.as_local(utc_next) if utc_next else None


def next_setting_utc(hass, entity_id=None):
    """ Returns the UTC datetime object of the next sun setting. """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return dt_util.str_to_datetime(
            state.attributes[STATE_ATTR_NEXT_SETTING])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_SETTING does not exist
        return None


def next_rising(hass, entity_id=None):
    """ Returns the local datetime object of the next sun rising. """
    utc_next = next_rising_utc(hass, entity_id)

    return dt_util.as_local(utc_next) if utc_next else None


def next_rising_utc(hass, entity_id=None):
    """ Returns the UTC datetime object of the next sun rising. """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return dt_util.str_to_datetime(
            state.attributes[STATE_ATTR_NEXT_RISING])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_RISING does not exist
        return None


def setup(hass, config):
    """ Tracks the state of the sun. """
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

    from astral import Location, GoogleGeocoder

    location = Location(('', '', latitude, longitude, hass.config.time_zone,
                         elevation or 0))

    if elevation is None:
        google = GoogleGeocoder()
        try:
            google._get_elevation(location)  # pylint: disable=protected-access
            _LOGGER.info(
                'Retrieved elevation from Google: %s', location.elevation)
        except urllib.error.URLError:
            # If no internet connection available etc.
            pass

    sun = Sun(hass, location)
    sun.point_in_time_listener(dt_util.utcnow())

    return True


class Sun(Entity):
    """ Represents the Sun. """

    entity_id = ENTITY_ID

    def __init__(self, hass, location):
        self.hass = hass
        self.location = location
        self._state = self.next_rising = self.next_setting = None

    @property
    def should_poll(self):
        """ We trigger updates ourselves after sunset/sunrise """
        return False

    @property
    def name(self):
        return "Sun"

    @property
    def state(self):
        if self.next_rising > self.next_setting:
            return STATE_ABOVE_HORIZON

        return STATE_BELOW_HORIZON

    @property
    def state_attributes(self):
        return {
            STATE_ATTR_NEXT_RISING: dt_util.datetime_to_str(self.next_rising),
            STATE_ATTR_NEXT_SETTING: dt_util.datetime_to_str(self.next_setting)
        }

    @property
    def next_change(self):
        """ Returns the datetime when the next change to the state is. """
        return min(self.next_rising, self.next_setting)

    def update_as_of(self, utc_point_in_time):
        """ Calculate sun state at a point in UTC time. """
        mod = -1
        while True:
            next_rising_dt = self.location.sunrise(
                utc_point_in_time + timedelta(days=mod), local=False)
            if next_rising_dt > utc_point_in_time:
                break
            mod += 1

        mod = -1
        while True:
            next_setting_dt = (self.location.sunset(
                utc_point_in_time + timedelta(days=mod), local=False))
            if next_setting_dt > utc_point_in_time:
                break
            mod += 1

        self.next_rising = next_rising_dt
        self.next_setting = next_setting_dt

    def point_in_time_listener(self, now):
        """ Called when the state of the sun has changed. """
        self.update_as_of(now)
        self.update_ha_state()

        # Schedule next update at next_change+1 second so sun state has changed
        track_point_in_utc_time(
            self.hass, self.point_in_time_listener,
            self.next_change + timedelta(seconds=1))


def create_event_listener(schedule, event_listener_data):
    """ Create a sun event listener based on the description. """

    negative_offset = False
    service = event_listener_data['service']
    offset_str = event_listener_data['offset']
    event = event_listener_data['event']

    if offset_str.startswith('-'):
        negative_offset = True
        offset_str = offset_str[1:]

    (hour, minute, second) = [int(x) for x in offset_str.split(':')]

    offset = timedelta(hours=hour, minutes=minute, seconds=second)

    if event == 'sunset':
        return SunsetEventListener(schedule, service, offset, negative_offset)

    return SunriseEventListener(schedule, service, offset, negative_offset)


# pylint: disable=too-few-public-methods
class SunEventListener(ServiceEventListener):
    """ This is the base class for sun event listeners. """

    def __init__(self, schedule, service, offset, negative_offset):
        ServiceEventListener.__init__(self, schedule, service)

        self.offset = offset
        self.negative_offset = negative_offset

    def __get_next_time(self, next_event):
        """
        Returns when the next time the service should be called.
        Taking into account the offset and which days the event should execute.
        """

        if self.negative_offset:
            next_time = next_event - self.offset
        else:
            next_time = next_event + self.offset

        while next_time < dt_util.now() or \
                next_time.weekday() not in self.my_schedule.days:
            next_time = next_time + timedelta(days=1)

        return next_time

    def schedule_next_event(self, hass, next_event):
        """ Schedule the event. """
        next_time = self.__get_next_time(next_event)

        # pylint: disable=unused-argument
        def execute(now):
            """ Call the execute method. """
            self.execute(hass)

        track_point_in_time(hass, execute, next_time)

        return next_time


# pylint: disable=too-few-public-methods
class SunsetEventListener(SunEventListener):
    """ This class is used the call a service when the sun sets. """
    def schedule(self, hass):
        """ Schedule the event """
        next_setting_dt = next_setting(hass)

        next_time_dt = self.schedule_next_event(hass, next_setting_dt)

        _LOGGER.info(
            'SunsetEventListener scheduled for %s, will call service %s.%s',
            next_time_dt, self.domain, self.service)


# pylint: disable=too-few-public-methods
class SunriseEventListener(SunEventListener):
    """ This class is used the call a service when the sun rises. """

    def schedule(self, hass):
        """ Schedule the event. """
        next_rising_dt = next_rising(hass)

        next_time_dt = self.schedule_next_event(hass, next_rising_dt)

        _LOGGER.info(
            'SunriseEventListener scheduled for %s, will call service %s.%s',
            next_time_dt, self.domain, self.service)
