from collections import namedtuple
from threading import RLock
from datetime import datetime

from app.EventBus import Event
from app.util import ensure_list, matcher

EVENT_STATE_CHANGED = "state_changed"

State = namedtuple("State", ['state','last_changed'])

class StateMachine(object):

    def __init__(self, eventbus):
        self.states = dict()
        self.eventbus = eventbus
        self.lock = RLock()

    def add_category(self, category, initial_state):
        self.states[category] = State(initial_state, datetime.now())

    def set_state(self, category, new_state):
        self.lock.acquire()

        assert category in self.states, "Category does not exist: {}".format(category)

        old_state = self.states[category]

        if old_state.state != new_state:
            self.states[category] = State(new_state, datetime.now())

            self.eventbus.fire(Event(EVENT_STATE_CHANGED, {'category':category, 'old_state':old_state, 'new_state':self.states[category]}))

        self.lock.release()

    def get_state(self, category):
        assert category in self.states, "Category does not exist: {}".format(category)

        return self.states[category]

    def get_states(self):
        for category in sorted(self.states.keys()):
            yield category, self.states[category].state, self.states[category].last_changed


def track_state_change(eventbus, category, from_state, to_state, action):
    from_state = ensure_list(from_state)
    to_state = ensure_list(to_state)

    def listener(event):
        assert isinstance(event, Event), "event needs to be of Event type"

        if category == event.data['category'] and \
                matcher(event.data['old_state'].state, from_state) and \
                matcher(event.data['new_state'].state, to_state):

            action(event.data['category'], event.data['old_state'], event.data['new_state'])

    eventbus.listen(EVENT_STATE_CHANGED, listener)
