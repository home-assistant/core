import logging

from collections import defaultdict
from itertools import chain
from threading import Thread, RLock

ALL_EVENTS = '*'

class EventBus(object):
    """ Class provides an eventbus. Allows code to listen for events and fire them. """

    def __init__(self):
        self.listeners = defaultdict(list)
        self.lock = RLock()
        self.logger = logging.getLogger(__name__)

    def fire(self, event):
        """ Fire an event. """
        assert isinstance(event, Event), "event needs to be an instance of Event"

        # We dont want the eventbus to be blocking,
        # We dont want the eventbus to crash when one of its listeners throws an Exception
        # So run in a thread
        def run():
            self.lock.acquire()

            self.logger.info("Event {}: {}".format(event.event_type, event.data))

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

        self.logger.info("New listener for event {}. Total: {}".format(event_type, len(self.listeners[event_type])))

        self.lock.release()


class Event(object):
    """ An event to be sent over the eventbus. """

    def __init__(self, event_type, data):
        self.event_type = event_type
        self.data = data
        self.stop_propegating = False
        self.remove_listener = False

    def __str__(self):
        return str([self.event_type, self.data])
