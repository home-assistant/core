"""
An event in the scheduler component that will call the service
every specified day at the time specified.
A time event need to have the type 'time', which service to call and at
which time.

{
    "type": "time",
    "service": "switch.turn_off",
    "time": "22:00"
}

"""

from datetime import datetime, timedelta
import logging

from homeassistant.components.scheduler import EventListener
from homeassistant.components import ATTR_ENTITY_ID

_LOGGER = logging.getLogger(__name__)


def create(schedule, event_listener_data):
    """ Create a TimeEvent based on the description """

    service = event_listener_data['service']
    (hour, minute) = [int(x) for x in event_listener_data['time'].split(':')]

    return TimeEventListener(schedule, service, hour, minute)


class TimeEventListener(EventListener):
    """ The time event that the scheduler uses """

    def __init__(self, schedule, service, hour, minute):
        EventListener.__init__(self, schedule)

        (self._domain, self._service) = service.split('.')

        self._hour = hour
        self._minute = minute

    def schedule(self, hass):
        """ Schedule this event so that it will be called """

        next_time = datetime.now().replace(hour=self._hour,
                                           minute=self._minute,
                                           second=0, microsecond=0)

        # Calculate the next time the event should be executed.
        # That is the next day that the schedule is configured to run
        while next_time < datetime.now() or \
                next_time.weekday() not in self._schedule.days:

            next_time = next_time + timedelta(days=1)

        # pylint: disable=unused-argument
        def execute(now):
            """ Call the execute method """
            self.execute(hass)

        hass.track_point_in_time(execute, next_time)

        _LOGGER.info(
            'TimeEventListener scheduled for {}, will call service {}.{}'
            .format(next_time, self._domain, self._service))

    def execute(self, hass):
        """ Call the service """
        data = {ATTR_ENTITY_ID: self._schedule.entity_ids}
        hass.call_service(self._domain, self._service, data)

        # Reschedule for next day
        self.schedule(hass)
