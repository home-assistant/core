"""
homeassistant
~~~~~~~~~~~~~

Module to control the lights based on devices at home and the state of the sun.

"""

import time
import logging
import threading
from collections import defaultdict, namedtuple
from datetime import datetime

logging.basicConfig(level=logging.INFO)

ALL_EVENTS = '*'
EVENT_HOMEASSISTANT_START = "homeassistant.start"
EVENT_HOMEASSISTANT_STOP = "homeassistant.stop"
EVENT_STATE_CHANGED = "state_changed"
EVENT_TIME_CHANGED = "time_changed"

TIMER_INTERVAL = 10  # seconds

# We want to be able to fire every time a minute starts (seconds=0).
# We want this so other modules can use that to make sure they fire
# every minute.
assert 60 % TIMER_INTERVAL == 0, "60 % TIMER_INTERVAL should be 0!"

DATE_STR_FORMAT = "%H:%M:%S %d-%m-%Y"


def start_home_assistant(eventbus):
    """ Start home assistant. """
    request_shutdown = threading.Event()

    eventbus.listen_once(EVENT_HOMEASSISTANT_STOP,
                         lambda event: request_shutdown.set())

    Timer(eventbus)

    eventbus.fire(EVENT_HOMEASSISTANT_START)

    while True:
        try:
            time.sleep(1)

            if request_shutdown.isSet():
                break

        except KeyboardInterrupt:
            break


def datetime_to_str(dattim):
    """ Converts datetime to a string format.

    @rtype : str
    """
    return dattim.strftime(DATE_STR_FORMAT)


def str_to_datetime(dt_str):
    """ Converts a string to a datetime object.

    @rtype: datetime
    """
    return datetime.strptime(dt_str, DATE_STR_FORMAT)


def ensure_list(parameter):
    """ Wraps parameter in a list if it is not one and returns it.

    @rtype : list
    """
    return parameter if isinstance(parameter, list) else [parameter]


def matcher(subject, pattern):
    """ Returns True if subject matches the pattern.

    Pattern is either a list of allowed subjects or a '*'.
    @rtype : bool
    """
    return '*' in pattern or subject in pattern


def create_state(state, attributes=None, last_changed=None):
    """ Creates a new state and initializes defaults where necessary. """
    attributes = attributes or {}
    last_changed = last_changed or datetime.now()

    return {'state': state,
            'attributes': attributes,
            'last_changed': datetime_to_str(last_changed)}


def track_state_change(eventbus, category, from_state, to_state, action):
    """ Helper method to track specific state changes. """
    from_state = ensure_list(from_state)
    to_state = ensure_list(to_state)

    def listener(event):
        """ State change listener that listens for specific state changes. """
        if category == event.data['category'] and \
                matcher(event.data['old_state']['state'], from_state) and \
                matcher(event.data['new_state']['state'], to_state):

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
        now = str_to_datetime(event.data['now'])

        if (point_in_time and now > point_in_time) or \
           (not point_in_time and
                matcher(now.year, year) and
                matcher(now.month, month) and
                matcher(now.day, day) and
                matcher(now.hour, hour) and
                matcher(now.minute, minute) and
                matcher(now.second, second)):

            # point_in_time are exact points in time
            # so we always remove it after fire
            if listen_once or point_in_time:
                event.eventbus.remove_listener(EVENT_TIME_CHANGED, listener)

            action(now)

    eventbus.listen(EVENT_TIME_CHANGED, listener)


Event = namedtuple("Event", ["eventbus", "event_type", "data"])


class EventBus(object):
    """ Class that allows code to listen for- and fire events. """

    def __init__(self):
        self._listeners = defaultdict(list)
        self.logger = logging.getLogger(__name__)

    @property
    def listeners(self):
        """ List of events that is being listened for. """
        return {key: len(self._listeners[key])
                for key in self._listeners.keys()
                if len(self._listeners[key]) > 0}

    def fire(self, event_type, event_data=None):
        """ Fire an event. """

        if not event_data:
            event_data = {}

        self.logger.info("EventBus:Event {}: {}".format(
                         event_type, event_data))

        def run():
            """ Fire listeners for event. """
            event = Event(self, event_type, event_data)

            # We do not use itertools.chain() because some listeners might
            # choose to remove themselves as a listener while being executed
            for listener in self._listeners[ALL_EVENTS] + \
                    self._listeners[event.event_type]:
                try:
                    listener(event)

                except Exception:  # pylint: disable=broad-except
                    self.logger.exception("EventBus:Exception in listener")

        # We dont want the eventbus to be blocking - run in a thread.
        threading.Thread(target=run).start()

    def listen(self, event_type, listener):
        """ Listen for all events or events of a specific type.

        To listen to all events specify the constant ``ALL_EVENTS``
        as event_type.
        """
        self._listeners[event_type].append(listener)

    def listen_once(self, event_type, listener):
        """ Listen once for event of a specific type.

        To listen to all events specify the constant ``ALL_EVENTS``
        as event_type.

        Note: at the moment it is impossible to remove a one time listener.
        """

        def onetime_listener(event):
            """ Removes listener from eventbus and then fires listener. """
            self.remove_listener(event_type, onetime_listener)

            listener(event)

        self.listen(event_type, onetime_listener)

    def remove_listener(self, event_type, listener):
        """ Removes a listener of a specific event_type. """
        try:
            self._listeners[event_type].remove(listener)

            if len(self._listeners[event_type]) == 0:
                del self._listeners[event_type]

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

    def remove_category(self, category):
        """ Removes a category from the state machine.

        Returns boolean to indicate if a category was removed. """
        try:
            del self.states[category]

            return True

        except KeyError:
            # if category does not exist
            return False

    def set_state(self, category, new_state, attributes=None):
        """ Set the state of a category, add category if it does not exist.

        Attributes is an optional dict to specify attributes of this state. """

        attributes = attributes or {}

        self.lock.acquire()

        # Add category if it does not exist
        if category not in self.states:
            self.states[category] = create_state(new_state, attributes)

        # Change state and fire listeners
        else:
            old_state = self.states[category]

            if old_state['state'] != new_state or \
               old_state['attributes'] != attributes:

                self.states[category] = create_state(new_state, attributes)

                self.eventbus.fire(EVENT_STATE_CHANGED,
                                   {'category': category,
                                    'old_state': old_state,
                                    'new_state': self.states[category]})

        self.lock.release()

    def get_state(self, category):
        """ Returns a dict (state,last_changed, attributes) describing
            the state of the specified category. """
        try:
            # Make a copy so people won't accidently mutate the state
            return dict(self.states[category])

        except KeyError:
            # If category does not exist
            return None

    def is_state(self, category, state):
        """ Returns True if category exists and is specified state. """
        cur_state = self.get_state(category)

        return cur_state and cur_state['state'] == state


class Timer(threading.Thread):
    """ Timer will sent out an event every TIMER_INTERVAL seconds. """

    def __init__(self, eventbus):
        threading.Thread.__init__(self)

        self.daemon = True
        self.eventbus = eventbus

        eventbus.listen_once(EVENT_HOMEASSISTANT_START,
                             lambda event: self.start())

    def run(self):
        """ Start the timer. """

        logging.getLogger(__name__).info("Timer:starting")

        last_fired_on_second = -1

        while True:
            # Sleep till it is the next time that we have to fire an event.
            # Aim for halfway through the second that matches TIMER_INTERVAL.
            # So if TIMER_INTERVAL is 10 fire at .5, 10.5, 20.5, etc seconds.
            # This will yield the best results because time.sleep() is not
            # 100% accurate because of non-realtime OS's
            now = datetime.now()

            if now.second % TIMER_INTERVAL > 0 or \
               now.second == last_fired_on_second:

                slp_seconds = TIMER_INTERVAL - now.second % TIMER_INTERVAL + \
                    .5 - now.microsecond/1000000.0

                time.sleep(slp_seconds)

                now = datetime.now()

            last_fired_on_second = now.second

            self.eventbus.fire(EVENT_TIME_CHANGED,
                               {'now': datetime_to_str(now)})


class HomeAssistantException(Exception):
    """ General Home Assistant exception occured. """
