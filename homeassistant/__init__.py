"""
homeassistant
~~~~~~~~~~~~~

Module to control the lights based on devices at home and the state of the sun.

"""

import time
import logging
import threading
from collections import defaultdict, namedtuple
from itertools import chain
from datetime import datetime

logging.basicConfig(level=logging.INFO)

ALL_EVENTS = '*'
EVENT_START = "start"
EVENT_STATE_CHANGED = "state_changed"
EVENT_TIME_CHANGED = "time_changed"

TIMER_INTERVAL = 10 # seconds

# We want to be able to fire every time a minute starts (seconds=0).
# We want this so other modules can use that to make sure they fire
# every minute.
assert 60 % TIMER_INTERVAL == 0, "60 % TIMER_INTERVAL should be 0!"

State = namedtuple("State", ['state','last_changed'])

def start_home_assistant(eventbus):
    """ Start home assistant. """
    Timer(eventbus)

    eventbus.fire(EVENT_START)

    while True:
        try:
            time.sleep(1)

        except KeyboardInterrupt:
            break

def ensure_list(parameter):
    """ Wraps parameter in a list if it is not one and returns it. """
    return parameter if isinstance(parameter, list) else [parameter]

def matcher(subject, pattern):
    """ Returns True if subject matches the pattern.

    Pattern is either a list of allowed subjects or a '*'.
    """
    return '*' in pattern or subject in pattern

def track_state_change(eventbus, category, from_state, to_state, action):
    """ Helper method to track specific state changes. """
    from_state = ensure_list(from_state)
    to_state = ensure_list(to_state)

    def listener(event):
        """ State change listener that listens for specific state changes. """
        if category == event.data['category'] and \
                matcher(event.data['old_state'].state, from_state) and \
                matcher(event.data['new_state'].state, to_state):

            action(event.data['category'],
                   event.data['old_state'],
                   event.data['new_state'])

    eventbus.listen(EVENT_STATE_CHANGED, listener)

# pylint: disable=too-many-arguments
def track_time_change(eventbus, action,
                      year='*', month='*', day='*',
                      hour='*', minute='*', second='*',
                      point_in_time=None, listen_once=False):
    """ Adds a listener that will listen for a specified or matching time. """
    year, month, day = ensure_list(year), ensure_list(month), ensure_list(day)
    hour, minute = ensure_list(hour), ensure_list(minute)
    second = ensure_list(second)

    def listener(event):
        """ Listens for matching time_changed events. """
        if  (point_in_time and event.data['now'] > point_in_time) or \
                (not point_in_time and \
                matcher(event.data['now'].year, year) and \
                matcher(event.data['now'].month, month) and \
                matcher(event.data['now'].day, day) and \
                matcher(event.data['now'].hour, hour) and \
                matcher(event.data['now'].minute, minute) and \
                matcher(event.data['now'].second, second)):

            # point_in_time are exact points in time
            # so we always remove it after fire
            if listen_once or point_in_time:
                event.eventbus.remove_listener(EVENT_TIME_CHANGED, listener)

            action(event.data['now'])

    eventbus.listen(EVENT_TIME_CHANGED, listener)

Event = namedtuple("Event", ["eventbus", "event_type", "data"])

class EventBus(object):
    """ Class that allows code to listen for- and fire events. """

    def __init__(self):
        self.listeners = defaultdict(list)
        self.logger = logging.getLogger(__name__)

    def fire(self, event_type, event_data=None):
        """ Fire an event. """

        if not event_data:
            event_data = {}

        self.logger.info("EventBus:Event {}: {}".format(
                                                    event_type, event_data))

        def run():
            """ Fire listeners for event. """
            event = Event(self, event_type, event_data)

            for listener in chain(self.listeners[ALL_EVENTS],
                                  self.listeners[event.event_type]):
                try:
                    listener(event)

                except Exception:  #pylint: disable=broad-except
                    self.logger.exception("EventBus:Exception in listener")

        # We dont want the eventbus to be blocking - run in a thread.
        threading.Thread(target=run).start()

    def listen(self, event_type, listener):
        """ Listen for all events or events of a specific type.

        To listen to all events specify the constant ``ALL_EVENTS``
        as event_type.
        """
        self.listeners[event_type].append(listener)

    def remove_listener(self, event_type, listener):
        """ Removes a listener of a specific event_type. """
        try:
            self.listeners[event_type].remove(listener)
        except ValueError:
            pass

class StateMachine(object):
    """ Helper class that tracks the state of different categories. """

    def __init__(self, eventbus):
        self.states = dict()
        self.eventbus = eventbus
        self.lock = threading.Lock()

    @property
    def categories(self):
        """ List of categories which states are being tracked. """
        return self.states.keys()

    def set_state(self, category, new_state):
        """ Set the state of a category, add category if it does not exist. """

        self.lock.acquire()

        # Add category if it does not exist
        if category not in self.states:
            self.states[category] = State(new_state, datetime.now())

        # Change state and fire listeners
        else:
            old_state = self.states[category]

            if old_state.state != new_state:
                self.states[category] = State(new_state, datetime.now())

                self.eventbus.fire(EVENT_STATE_CHANGED,
                    {'category':category,
                     'old_state':old_state,
                     'new_state':self.states[category]})

        self.lock.release()

    def is_state(self, category, state):
        """ Returns True if category is specified state. """
        self._validate_category(category)

        return self.get_state(category).state == state

    def get_state(self, category):
        """ Returns a tuple (state,last_changed) describing
            the state of the specified category. """
        self._validate_category(category)

        return self.states[category]

    def _validate_category(self, category):
        """ Helper function to throw an exception
            when the category does not exist. """
        if category not in self.states:
            raise CategoryDoesNotExistException(
                    "Category {} does not exist.".format(category))

class Timer(threading.Thread):
    """ Timer will sent out an event every TIMER_INTERVAL seconds. """

    def __init__(self, eventbus):
        threading.Thread.__init__(self)

        self.daemon = True
        self.eventbus = eventbus

        eventbus.listen(EVENT_START, lambda event: self.start())

    def run(self):
        """ Start the timer. """

        logging.getLogger(__name__).info("Timer:starting")

        while True:
            while True:
                time.sleep(1)

                now = datetime.now()

                if now.second % TIMER_INTERVAL == 0:
                    break

            self.eventbus.fire(EVENT_TIME_CHANGED, {'now':now})

class HomeAssistantException(Exception):
    """ General Home Assistant exception occured. """

class CategoryDoesNotExistException(HomeAssistantException):
    """ Specified category does not exist within the state machine. """


