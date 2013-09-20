import logging

from collections import defaultdict
from itertools import chain
from threading import Thread, RLock

ALL_EVENTS = '*'

class EventBus:
	def __init__(self):
		self.listeners = defaultdict(list)
		self.lock = RLock()
		self.logger =logging.getLogger(__name__)
		
	def fire(self, event):
		assert isinstance(event, Event), "event needs to be an instance of Event"

		# We dont want the eventbus to be blocking, 
		# We dont want the eventbus to crash when one of its listeners throws an Exception
		# So run in a thread
		def run():
			self.lock.acquire()

			self.logger.info("{} event received: {}".format(event.eventType, event.data))

			for callback in chain(self.listeners[ALL_EVENTS], self.listeners[event.eventType]):
				callback(event)

				if event.removeListener:
					if callback in self.listeners[ALL_EVENTS]:
						self.listeners[ALL_EVENTS].remove(callback)

					if callback in self.listeners[event.eventType]:
						self.listeners[event.eventType].remove(callback)

					event.removeListener = False

				if event.stopPropegating:
					break

			self.lock.release()

		Thread(target=run).start()

	def listen(self, event_type, callback):
		self.lock.acquire()

		self.listeners[event_type].append(callback)

		self.logger.info("New listener added for event {}. Total: {}".format(event_type, len(self.listeners[event_type])))

		self.lock.release()


class Event:
	def __init__(self, eventType, data):
		self.eventType = eventType
		self.data = data
		self.stopPropegating = False
		self.removeListener = False

	def __str__(self):
		return str([self.eventType, self.data])

