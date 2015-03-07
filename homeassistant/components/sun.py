"""
homeassistant.components.sun
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to keep track of the sun.


Event listener
--------------
The suns event listener will call the service
when the sun rises or sets with an offset.
The sun evnt need to have the type 'sun', which service to call,
which event (sunset or sunrise) and the offset.

{
    "type": "sun",
    "service": "switch.turn_on",
    "event": "sunset",
    "offset": "-01:00:00"
}


"""
import logging
from datetime import datetime, timedelta

import homeassistant as ha
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers import validate_config
from homeassistant.util import str_to_datetime, datetime_to_str

from homeassistant.components.scheduler import ServiceEventListener

DEPENDENCIES = []
DOMAIN = "sun"
ENTITY_ID = "sun.sun"

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
    """ Returns the datetime object representing the next sun setting. """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return str_to_datetime(state.attributes[STATE_ATTR_NEXT_SETTING])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_SETTING does not exist
        return None


def next_rising(hass, entity_id=None):
    """ Returns the datetime object representing the next sun rising. """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return str_to_datetime(state.attributes[STATE_ATTR_NEXT_RISING])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_RISING does not exist
        return None


def setup(hass, config):
    """ Tracks the state of the sun. """
    logger = logging.getLogger(__name__)

    if not validate_config(config,
                           {ha.DOMAIN: [CONF_LATITUDE, CONF_LONGITUDE]},
                           logger):
        return False

    try:
        import ephem
    except ImportError:
        logger.exception("Error while importing dependency ephem.")
        return False

    sun = ephem.Sun()  # pylint: disable=no-member

    latitude = str(config[ha.DOMAIN][CONF_LATITUDE])
    longitude = str(config[ha.DOMAIN][CONF_LONGITUDE])

    # Validate latitude and longitude
    observer = ephem.Observer()

    errors = []

    try:
        observer.lat = latitude  # pylint: disable=assigning-non-slot
    except ValueError:
        errors.append("invalid value for latitude given: {}".format(latitude))

    try:
        observer.long = longitude  # pylint: disable=assigning-non-slot
    except ValueError:
        errors.append("invalid value for latitude given: {}".format(latitude))

    if errors:
        logger.error("Error setting up: %s", ", ".join(errors))
        return False

    def update_sun_state(now):
        """ Method to update the current state of the sun and
            set time of next setting and rising. """
        utc_offset = datetime.utcnow() - datetime.now()
        utc_now = now + utc_offset

        observer = ephem.Observer()
        observer.lat = latitude  # pylint: disable=assigning-non-slot
        observer.long = longitude  # pylint: disable=assigning-non-slot

        next_rising_dt = ephem.localtime(
            observer.next_rising(sun, start=utc_now))
        next_setting_dt = ephem.localtime(
            observer.next_setting(sun, start=utc_now))

        if next_rising_dt > next_setting_dt:
            new_state = STATE_ABOVE_HORIZON
            next_change = next_setting_dt

        else:
            new_state = STATE_BELOW_HORIZON
            next_change = next_rising_dt

        logger.info("%s. Next change: %s",
                    new_state, next_change.strftime("%H:%M"))

        state_attributes = {
            STATE_ATTR_NEXT_RISING: datetime_to_str(next_rising_dt),
            STATE_ATTR_NEXT_SETTING: datetime_to_str(next_setting_dt)
        }

        hass.states.set(ENTITY_ID, new_state, state_attributes)

        # +1 second so Ephem will report it has set
        hass.track_point_in_time(update_sun_state,
                                 next_change + timedelta(seconds=1))

    update_sun_state(datetime.now())

    return True


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

        while next_time < datetime.now() or \
                next_time.weekday() not in self.my_schedule.days:
            next_time = next_time + timedelta(days=1)

        return next_time

    def schedule_next_event(self, hass, next_event):
        """ Schedule the event """
        next_time = self.__get_next_time(next_event)

        # pylint: disable=unused-argument
        def execute(now):
            """ Call the execute method """
            self.execute(hass)

        hass.track_point_in_time(execute, next_time)

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
        """ Schedule the event """
        next_rising_dt = next_rising(hass)

        next_time_dt = self.schedule_next_event(hass, next_rising_dt)

        _LOGGER.info(
            'SunriseEventListener scheduled for %s, will call service %s.%s',
            next_time_dt, self.domain, self.service)
