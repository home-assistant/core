"""
homeassistant.common
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module provides the core components of homeassistant.

"""

import logging
from collections import defaultdict, namedtuple
from itertools import chain
from threading import Thread, RLock
from datetime import datetime

ALL_EVENTS = '*'
EVENT_STATE_CHANGED = "state_changed"
EVENT_START = "start"
EVENT_SHUTDOWN = "shutdown"

State = namedtuple("State", ['state','last_changed'])

def ensure_list(parameter):
    """ Wraps parameter in a list if it is not one and returns it. """
    return parameter if isinstance(parameter, list) else [parameter]

def matcher(subject, pattern):
    """ Returns True if subject matches the pattern.
        Pattern is either a list of allowed subjects or a '*'. """
    return '*' in pattern or subject in pattern

def track_state_change(eventbus, category, from_state, to_state, action):
    """ Helper method to track specific state changes. """
    from_state = ensure_list(from_state)
    to_state = ensure_list(to_state)

    def listener(event):
        """ State change listener that listens for specific state changes. """
        assert isinstance(event, Event), "event needs to be of Event type"

        if category == event.data['category'] and \
                matcher(event.data['old_state'].state, from_state) and \
                matcher(event.data['new_state'].state, to_state):

            action(event.data['category'], event.data['old_state'], event.data['new_state'])

    eventbus.listen(EVENT_STATE_CHANGED, listener)


class EventBus(object):
    """ Class provides an eventbus. Allows code to listen for events and fire them. """

    def __init__(self):
        self.listeners = defaultdict(list)
        self.lock = RLock()
        self.logger = logging.getLogger(__name__)

    def fire(self, event):
        """ Fire an event. """
        assert isinstance(event, Event), "event needs to be an instance of Event"

        def run():
            """ We dont want the eventbus to be blocking,
                We dont want the eventbus to crash when one of its listeners throws an Exception
                So run in a thread. """
            self.lock.acquire()

            self.logger.info("EventBus:Event {}: {}".format(event.event_type, event.data))

            for callback in chain(self.listeners[ALL_EVENTS], self.listeners[event.event_type]):
                callback(event)

                if event.remove_listener:
                    if callback in self.listeners[ALL_EVENTS]:
                        self.listeners[ALL_EVENTS].remove(callback)

                    if callback in self.listeners[event.event_type]:
                        self.listeners[event.event_type].remove(callback)

                    event.remove_listener = False

                if event.stop_propegating:
                    break

            self.lock.release()

        Thread(target=run).start()

    def listen(self, event_type, callback):
        """ Listen for all events or events of a specific type.

            To listen to all events specify the constant ``ALL_EVENTS`` as event_type. """
        self.lock.acquire()

        self.listeners[event_type].append(callback)

        self.lock.release()

class Event(object):
    """ An event to be sent over the eventbus. """

    def __init__(self, event_type, data=None):
        self.event_type = event_type
        self.data = {} if data is None else data
        self.stop_propegating = False
        self.remove_listener = False

    def __str__(self):
        return str([self.event_type, self.data])

class StateMachine(object):
    """ Helper class that tracks the state of different objects. """

    def __init__(self, eventbus):
        self.states = dict()
        self.eventbus = eventbus
        self.lock = RLock()

    def add_category(self, category, initial_state):
        """ Add a category which state we will keep track off. """
        self.states[category] = State(initial_state, datetime.now())

    def set_state(self, category, new_state):
        """ Set the state of a category. """
        self._validate_category(category)

        self.lock.acquire()

        old_state = self.states[category]

        if old_state.state != new_state:
            self.states[category] = State(new_state, datetime.now())

            self.eventbus.fire(Event(EVENT_STATE_CHANGED, {'category':category, 'old_state':old_state, 'new_state':self.states[category]}))

        self.lock.release()

    def is_state(self, category, state):
        """ Returns True if category is specified state. """
        self._validate_category(category)

        return self.get_state(category).state == state

    def get_state(self, category):
        """ Returns a tuple (state,last_changed) describing the state of the specified category. """
        self._validate_category(category)

        return self.states[category]

    def get_states(self):
        """ Returns a list of tuples (category, state, last_changed) sorted by category. """
        return [(category, self.states[category].state, self.states[category].last_changed) for category in sorted(self.states.keys())]

    def _validate_category(self, category):
        if category not in self.states:
            raise CategoryDoesNotExistException("Category {} does not exist.".format(category))


class HomeAssistantException(Exception):
    """ General Home Assistant exception occured. """

class CategoryDoesNotExistException(HomeAssistantException):
    """ Specified category does not exist within the state machine. """
