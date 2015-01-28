"""
An event in the scheduler component that will call the service
every specified day at the time specified.
A time event need to have the type 'time', which service to call and at
which time.

{
    "type": "time",
    "service": "switch.turn_off",
    "time": "22:00:00"
}

"""

from datetime import datetime, timedelta
import logging

from homeassistant.components.scheduler import ServiceEventListener

_LOGGER = logging.getLogger(__name__)


def create_event_listener(schedule, event_listener_data):
    """ Create a TimeEvent based on the description """

    service = event_listener_data['service']
    (hour, minute, second) = [int(x) for x in
                              event_listener_data['time'].split(':')]

    return TimeEventListener(schedule, service, hour, minute, second)


# pylint: disable=too-few-public-methods
class TimeEventListener(ServiceEventListener):
    """ The time event that the scheduler uses """

    # pylint: disable=too-many-arguments
    def __init__(self, schedule, service, hour, minute, second):
        ServiceEventListener.__init__(self, schedule, service)

        self.hour = hour
        self.minute = minute
        self.second = second

    def schedule(self, hass):
        """ Schedule this event so that it will be called """

        next_time = datetime.now().replace(hour=self.hour,
                                           minute=self.minute,
                                           second=self.second,
                                           microsecond=0)

        # Calculate the next time the event should be executed.
        # That is the next day that the schedule is configured to run
        while next_time < datetime.now() or \
                next_time.weekday() not in self.my_schedule.days:

            next_time = next_time + timedelta(days=1)

        # pylint: disable=unused-argument
        def execute(now):
            """ Call the execute method """
            self.execute(hass)

        hass.track_point_in_time(execute, next_time)

        _LOGGER.info(
            'TimeEventListener scheduled for %s, will call service %s.%s',
            next_time, self.domain, self.service)
