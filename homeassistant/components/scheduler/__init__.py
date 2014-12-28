"""
homeassistant.components.scheduler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A component that will act as a scheduler and performe actions based
on the events in the schedule.

It will read a json object from schedule.json in the config dir
and create a schedule based on it.
Each schedule is a JSON with the keys id, name, description,
entity_ids, and events.
- days is an array with the weekday number (monday=0) that the schdule
    is active
- entity_ids an array with entity ids that the events in the schedule should
    effect (can also be groups)
- events is an array of objects that describe the different events that is
    supported. Read in the events descriptions for more information
"""
import logging
import json

from homeassistant.loader import get_component

from homeassistant.const import ATTR_ENTITY_ID

# The domain of your component. Should be equal to the name of your component
DOMAIN = 'scheduler'

# List of component names (string) your component depends upon
# If you are setting up a group but not using a group for anything,
# don't depend on group
DEPENDENCIES = ['sun']

_LOGGER = logging.getLogger(__name__)

_SCHEDULE_FILE = 'schedule.json'


# pylint: disable=unused-argument
def setup(hass, config):
    """ Create the schedules """

    def setup_schedule(schedule_data):
        """ setup a schedule based on the description """

        schedule = Schedule(schedule_data['id'],
                            name=schedule_data['name'],
                            description=schedule_data['description'],
                            entity_ids=schedule_data['entity_ids'],
                            days=schedule_data['days'])

        for event_data in schedule_data['events']:
            event_listener_type = \
                get_component('scheduler.{}'.format(event_data['type']))
            event_listener = event_listener_type.create(schedule, event_data)
            schedule.add_event_listener(event_listener)

        schedule.schedule(hass)
        return True

    with open(hass.get_config_path(_SCHEDULE_FILE)) as schedule_file:
        schedule_descriptions = json.load(schedule_file)

    for schedule_description in schedule_descriptions:
        if not setup_schedule(schedule_description):
            return False

    return True


class Schedule(object):
    """ A Schedule """

    # pylint: disable=too-many-arguments
    def __init__(self, schedule_id, name=None, description=None,
                 entity_ids=None, days=None):

        self.schedule_id = schedule_id
        self.name = name
        self.description = description

        self.entity_ids = entity_ids or []

        self.days = days or [0, 1, 2, 3, 4, 5, 6]

        self.__event_listeners = []

    def add_event_listener(self, event_listener):
        """ Add a event to the schedule """
        self.__event_listeners.append(event_listener)

    def schedule(self, hass):
        """ Schedule all the events in the schdule """
        for event in self.__event_listeners:
            event.schedule(hass)


class EventListener(object):
    """ The base EventListner class that the schedule uses """
    def __init__(self, schedule):
        self.my_schedule = schedule

    def schedule(self, hass):
        """ Schedule the event """
        pass

    def execute(self, hass):
        """ execute the event """
        pass


# pylint: disable=too-few-public-methods
class ServiceEventListener(EventListener):
    """ A EventListner that calls a service when executed """

    def __init__(self, schdule, service):
        EventListener.__init__(self, schdule)

        (self.domain, self.service) = service.split('.')

    def execute(self, hass):
        """ Call the service """
        data = {ATTR_ENTITY_ID: self.my_schedule.entity_ids}
        hass.call_service(self.domain, self.service, data)

        # Reschedule for next day
        self.schedule(hass)
