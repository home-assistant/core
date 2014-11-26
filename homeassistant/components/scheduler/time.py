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

from homeassistant.components.scheduler import Event

_LOGGER = logging.getLogger(__name__)


def create(schedule, description):
    """ Create a TimeEvent based on the description """

    service = description['service']
    (hour, minute) = [int(x) for x in description['time'].split(':')]

    return TimeEvent(schedule, service, hour, minute)


class TimeEvent(Event):
    """ The time event that the scheduler uses """

    def __init__(self, schedule, service, hour, minute):
        Event.__init__(self, schedule)

        (self._domain, self._service) = service.split('.')

        self._hour = hour
        self._minute = minute

        print(self._domain, self._service)

    def schedule(self):
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
            self.execute()

        self._schedule.hass.track_point_in_time(execute, next_time)

        _LOGGER.info('point in time scheduled at {} for {}'
                     .format(next_time, ""))

    def execute(self):
        """ Call the service """
        # data = {ATTR_ENTITY_ID: self._schedule.entity_ids}
        # self._schedule.hass.call_service(self._domain, self._service, data)
        print("executoing time", self._domain, self._service)
        self.schedule()
