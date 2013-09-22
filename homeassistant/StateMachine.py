from collections import namedtuple
from threading import RLock
from datetime import datetime

from homeassistant.EventBus import Event
from homeassistant.util import matcher

EVENT_STATE_CHANGED = "state_changed"

State = namedtuple("State", ['state','last_changed'])

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
        self.lock.acquire()

        assert category in self.states, "Category does not exist: {}".format(category)

        old_state = self.states[category]

        if old_state.state != new_state:
            self.states[category] = State(new_state, datetime.now())

            self.eventbus.fire(Event(EVENT_STATE_CHANGED, {'category':category, 'old_state':old_state, 'new_state':self.states[category]}))

        self.lock.release()

    def is_state(self, category, state):
        """ Returns True if category is specified state. """
        assert category in self.states, "Category does not exist: {}".format(category)

        return self.get_state(category).state == state

    def get_state(self, category):
        """ Returns a tuple (state,last_changed) describing the state of the specified category. """
        assert category in self.states, "Category does not exist: {}".format(category)

        return self.states[category]

    def get_states(self):
        """ Returns a list of tuples (category, state, last_changed) sorted by category. """
        return [(category, self.states[category].state, self.states[category].last_changed) for category in sorted(self.states.keys())]


def track_state_change(eventbus, category, from_state, to_state, action):
    """ Helper method to track specific state changes. """
    from_state = list(from_state)
    to_state = list(to_state)

    def listener(event):
        assert isinstance(event, Event), "event needs to be of Event type"

        if category == event.data['category'] and \
                matcher(event.data['old_state'].state, from_state) and \
                matcher(event.data['new_state'].state, to_state):

            action(event.data['category'], event.data['old_state'], event.data['new_state'])

    eventbus.listen(EVENT_STATE_CHANGED, listener)
