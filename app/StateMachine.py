from collections import defaultdict, namedtuple
from threading import RLock
from datetime import datetime

from app.EventBus import Event
from app.util import ensure_list, matcher

EVENT_STATE_CHANGED = "state_changed"

state = namedtuple("State", ['state','last_changed'])

class StateMachine:

	def __init__(self, eventBus):
		self.states = dict()
		self.eventBus = eventBus
		self.lock = RLock()

	def add_category(self, category, initialState):
		self.states[category] = state(initialState, datetime.now())

	def set_state(self, category, newState):
		self.lock.acquire()

		assert category in self.states, "Category does not exist: {}".format(category)
		
		oldState = self.states[category]

		if oldState.state != newState:
			self.states[category] = state(newState, datetime.now())

			self.eventBus.fire(Event(EVENT_STATE_CHANGED, {'category':category, 'oldState':oldState, 'newState':self.states[category]}))

		self.lock.release()

	def get_state(self, category):
		assert category in self.states, "Category does not exist: {}".format(category)

		return self.states[category]


def track_state_change(eventBus, category, fromState, toState, action):
	fromState = ensure_list(fromState)
	toState = ensure_list(toState)

	def listener(event):
		assert isinstance(event, Event), "event needs to be of Event type"

		if category == event.data['category'] and \
			matcher(event.data['oldState'].state, fromState) and \
			matcher(event.data['newState'].state, toState):
			
			action(event.data['category'], event.data['oldState'], event.data['newState'])

	eventBus.listen(EVENT_STATE_CHANGED, listener)

