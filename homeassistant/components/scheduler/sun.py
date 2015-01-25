"""
An event in the scheduler component that will call the service
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

from datetime import datetime, timedelta
import logging

from homeassistant.components.scheduler import ServiceEventListener
import homeassistant.components.sun as sun

_LOGGER = logging.getLogger(__name__)


def create(schedule, event_listener_data):
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
        next_setting = sun.next_setting(hass)

        next_time = self.schedule_next_event(hass, next_setting)

        _LOGGER.info(
            'SunsetEventListener scheduled for %s, will call service %s.%s',
            next_time, self.domain, self.service)


# pylint: disable=too-few-public-methods
class SunriseEventListener(SunEventListener):
    """ This class is used the call a service when the sun rises. """

    def schedule(self, hass):
        """ Schedule the event """
        next_rising = sun.next_rising(hass)

        next_time = self.schedule_next_event(hass, next_rising)

        _LOGGER.info(
            'SunriseEventListener scheduled for %s, will call service %s.%s',
            next_time, self.domain, self.service)
