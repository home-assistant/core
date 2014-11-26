"""
homeassistant
~~~~~~~~~~~~~

Home Assistant is a Home Automation framework for observing the state
of entities and react to changes.
"""

import os
import time
import logging
import threading
import enum
import re
import datetime as dt
import functools as ft

import homeassistant.util as util

MATCH_ALL = '*'

DOMAIN = "homeassistant"

SERVICE_HOMEASSISTANT_STOP = "stop"

EVENT_HOMEASSISTANT_START = "homeassistant_start"
EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"
EVENT_STATE_CHANGED = "state_changed"
EVENT_TIME_CHANGED = "time_changed"
EVENT_CALL_SERVICE = "call_service"

ATTR_NOW = "now"
ATTR_DOMAIN = "domain"
ATTR_SERVICE = "service"

CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_TYPE = "type"
CONF_HOST = "host"
CONF_HOSTS = "hosts"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# How often time_changed event should fire
TIMER_INTERVAL = 10  # seconds

# Number of worker threads
POOL_NUM_THREAD = 4

# Pattern for validating entity IDs (format: <domain>.<entity>)
ENTITY_ID_PATTERN = re.compile(r"^(?P<domain>\w+)\.(?P<entity>\w+)$")

_LOGGER = logging.getLogger(__name__)


class HomeAssistant(object):
    """ Core class to route all communication to right components. """

    def __init__(self):
        self._pool = pool = create_worker_pool()

        self.bus = EventBus(pool)
        self.services = ServiceRegistry(self.bus, pool)
        self.states = StateMachine(self.bus)

        self.config_dir = os.path.join(os.getcwd(), 'config')

    def get_config_path(self, path):
        """ Returns path to the file within the config dir. """
        return os.path.join(self.config_dir, path)

    def start(self):
        """ Start home assistant. """
        Timer(self)

        self.bus.fire(EVENT_HOMEASSISTANT_START)

    def block_till_stopped(self):
        """ Will register service homeassistant/stop and
            will block until called. """
        request_shutdown = threading.Event()

        self.services.register(DOMAIN, SERVICE_HOMEASSISTANT_STOP,
                               lambda service: request_shutdown.set())

        while not request_shutdown.isSet():
            try:
                time.sleep(1)

            except KeyboardInterrupt:
                break

        self.stop()

    def call_service(self, domain, service, service_data=None):
        """ Fires event to call specified service. """
        event_data = service_data or {}
        event_data[ATTR_DOMAIN] = domain
        event_data[ATTR_SERVICE] = service

        self.bus.fire(EVENT_CALL_SERVICE, event_data)

    def get_entity_ids(self, domain_filter=None):
        """ Returns known entity ids. """
        if domain_filter:
            return [entity_id for entity_id in self.states.entity_ids
                    if entity_id.startswith(domain_filter)]
        else:
            return self.states.entity_ids

    def track_state_change(self, entity_ids, action,
                           from_state=None, to_state=None):
        """
        Track specific state changes.
        entity_ids, from_state and to_state can be string or list.
        Use list to match multiple.
        """
        from_state = _process_match_param(from_state)
        to_state = _process_match_param(to_state)

        # Ensure it is a list with entity ids we want to match on
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        @ft.wraps(action)
        def state_listener(event):
            """ The listener that listens for specific state changes. """
            if event.data['entity_id'] in entity_ids and \
                    'old_state' in event.data and \
                    _matcher(event.data['old_state'].state, from_state) and \
                    _matcher(event.data['new_state'].state, to_state):

                action(event.data['entity_id'],
                       event.data['old_state'],
                       event.data['new_state'])

        self.bus.listen(EVENT_STATE_CHANGED, state_listener)

    def track_point_in_time(self, action, point_in_time):
        """
        Adds a listener that fires once at or after a spefic point in time.
        """

        @ft.wraps(action)
        def point_in_time_listener(event):
            """ Listens for matching time_changed events. """
            now = event.data[ATTR_NOW]

            if now >= point_in_time and \
               not hasattr(point_in_time_listener, 'run'):

                # Set variable so that we will never run twice.
                # Because the event bus might have to wait till a thread comes
                # available to execute this listener it might occur that the
                # listener gets lined up twice to be executed. This will make
                # sure the second time it does nothing.
                point_in_time_listener.run = True

                self.bus.remove_listener(EVENT_TIME_CHANGED,
                                         point_in_time_listener)

                action(now)

        self.bus.listen(EVENT_TIME_CHANGED, point_in_time_listener)

    # pylint: disable=too-many-arguments
    def track_time_change(self, action,
                          year=None, month=None, day=None,
                          hour=None, minute=None, second=None):
        """ Adds a listener that will fire if time matches a pattern. """

        # We do not have to wrap the function with time pattern matching logic
        # if no pattern given
        if any((val is not None for val in
                (year, month, day, hour, minute, second))):

            pmp = _process_match_param
            year, month, day = pmp(year), pmp(month), pmp(day)
            hour, minute, second = pmp(hour), pmp(minute), pmp(second)

            @ft.wraps(action)
            def time_listener(event):
                """ Listens for matching time_changed events. """
                now = event.data[ATTR_NOW]

                mat = _matcher

                if mat(now.year, year) and \
                   mat(now.month, month) and \
                   mat(now.day, day) and \
                   mat(now.hour, hour) and \
                   mat(now.minute, minute) and \
                   mat(now.second, second):

                    action(now)

        else:
            @ft.wraps(action)
            def time_listener(event):
                """ Fires every time event that comes in. """
                action(event.data[ATTR_NOW])

        self.bus.listen(EVENT_TIME_CHANGED, time_listener)

    def listen_once_event(self, event_type, listener):
        """ Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Note: at the moment it is impossible to remove a one time listener.
        """
        @ft.wraps(listener)
        def onetime_listener(event):
            """ Removes listener from eventbus and then fires listener. """
            if not hasattr(onetime_listener, 'run'):
                # Set variable so that we will never run twice.
                # Because the event bus might have to wait till a thread comes
                # available to execute this listener it might occur that the
                # listener gets lined up twice to be executed.
                # This will make sure the second time it does nothing.
                onetime_listener.run = True

                self.bus.remove_listener(event_type, onetime_listener)

                listener(event)

        self.bus.listen(event_type, onetime_listener)

    def stop(self):
        """ Stops Home Assistant and shuts down all threads. """
        _LOGGER.info("Stopping")

        self.bus.fire(EVENT_HOMEASSISTANT_STOP)

        # Wait till all responses to homeassistant_stop are done
        self._pool.block_till_done()

        self._pool.stop()


def _process_match_param(parameter):
    """ Wraps parameter in a list if it is not one and returns it. """
    if not parameter or parameter == MATCH_ALL:
        return MATCH_ALL
    elif isinstance(parameter, list):
        return parameter
    else:
        return [parameter]


def _matcher(subject, pattern):
    """ Returns True if subject matches the pattern.

    Pattern is either a list of allowed subjects or a `MATCH_ALL`.
    """
    return MATCH_ALL == pattern or subject in pattern


class JobPriority(util.OrderedEnum):
    """ Provides priorities for bus events. """
    # pylint: disable=no-init,too-few-public-methods

    EVENT_SERVICE = 1
    EVENT_STATE = 2
    EVENT_TIME = 3
    EVENT_DEFAULT = 4

    @staticmethod
    def from_event_type(event_type):
        """ Returns a priority based on event type. """
        if event_type == EVENT_TIME_CHANGED:
            return JobPriority.EVENT_TIME
        elif event_type == EVENT_STATE_CHANGED:
            return JobPriority.EVENT_STATE
        elif event_type == EVENT_CALL_SERVICE:
            return JobPriority.EVENT_SERVICE
        else:
            return JobPriority.EVENT_DEFAULT


def create_worker_pool(thread_count=POOL_NUM_THREAD):
    """ Creates a worker pool to be used. """

    def job_handler(job):
        """ Called whenever a job is available to do. """
        try:
            func, arg = job
            func(arg)
        except Exception:  # pylint: disable=broad-except
            # Catch any exception our service/event_listener might throw
            # We do not want to crash our ThreadPool
            _LOGGER.exception("BusHandler:Exception doing job")

    def busy_callback(current_jobs, pending_jobs_count):
        """ Callback to be called when the pool queue gets too big. """

        _LOGGER.error(
            "WorkerPool:All %d threads are busy and %d jobs pending",
            thread_count, pending_jobs_count)

        for start, job in current_jobs:
            _LOGGER.error("WorkerPool:Current job from %s: %s",
                          util.datetime_to_str(start), job)

    return util.ThreadPool(thread_count, job_handler, busy_callback)


class EventOrigin(enum.Enum):
    """ Distinguish between origin of event. """
    # pylint: disable=no-init,too-few-public-methods

    local = "LOCAL"
    remote = "REMOTE"

    def __str__(self):
        return self.value


# pylint: disable=too-few-public-methods
class Event(object):
    """ Represents an event within the Bus. """

    __slots__ = ['event_type', 'data', 'origin']

    def __init__(self, event_type, data=None, origin=EventOrigin.local):
        self.event_type = event_type
        self.data = data or {}
        self.origin = origin

    def __repr__(self):
        # pylint: disable=maybe-no-member
        if self.data:
            return "<Event {}[{}]: {}>".format(
                self.event_type, str(self.origin)[0],
                util.repr_helper(self.data))
        else:
            return "<Event {}[{}]>".format(self.event_type,
                                           str(self.origin)[0])


class EventBus(object):
    """ Class that allows different components to communicate via services
    and events.
    """

    def __init__(self, pool=None):
        self._listeners = {}
        self._lock = threading.Lock()
        self._pool = pool or create_worker_pool()

    @property
    def listeners(self):
        """ Dict with events that is being listened for and the number
        of listeners.
        """
        with self._lock:
            return {key: len(self._listeners[key])
                    for key in self._listeners}

    def fire(self, event_type, event_data=None, origin=EventOrigin.local):
        """ Fire an event. """
        with self._lock:
            # Copy the list of the current listeners because some listeners
            # remove themselves as a listener while being executed which
            # causes the iterator to be confused.
            get = self._listeners.get
            listeners = get(MATCH_ALL, []) + get(event_type, [])

            event = Event(event_type, event_data, origin)

            _LOGGER.info("Bus:Handling %s", event)

            if not listeners:
                return

            for func in listeners:
                self._pool.add_job(JobPriority.from_event_type(event_type),
                                   (func, event))

    def listen(self, event_type, listener):
        """ Listen for all events or events of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.
        """
        with self._lock:
            if event_type in self._listeners:
                self._listeners[event_type].append(listener)
            else:
                self._listeners[event_type] = [listener]

    def remove_listener(self, event_type, listener):
        """ Removes a listener of a specific event_type. """
        with self._lock:
            try:
                self._listeners[event_type].remove(listener)

                # delete event_type list if empty
                if not self._listeners[event_type]:
                    self._listeners.pop(event_type)

            except (KeyError, ValueError):
                # KeyError is key event_type listener did not exist
                # ValueError if listener did not exist within event_type
                pass


class State(object):
    """ Object to represent a state within the state machine. """

    __slots__ = ['entity_id', 'state', 'attributes', 'last_changed']

    def __init__(self, entity_id, state, attributes=None, last_changed=None):
        if not ENTITY_ID_PATTERN.match(entity_id):
            raise InvalidEntityFormatError((
                "Invalid entity id encountered: {}. "
                "Format should be <domain>.<entity>").format(entity_id))

        self.entity_id = entity_id
        self.state = state
        self.attributes = attributes or {}
        last_changed = last_changed or dt.datetime.now()

        # Strip microsecond from last_changed else we cannot guarantee
        # state == State.from_dict(state.as_dict())
        # This behavior occurs because to_dict uses datetime_to_str
        # which strips microseconds
        if last_changed.microsecond:
            self.last_changed = last_changed - dt.timedelta(
                microseconds=last_changed.microsecond)
        else:
            self.last_changed = last_changed

    def copy(self):
        """ Creates a copy of itself. """
        return State(self.entity_id, self.state,
                     dict(self.attributes), self.last_changed)

    def as_dict(self):
        """ Converts State to a dict to be used within JSON.
        Ensures: state == State.from_dict(state.as_dict()) """

        return {'entity_id': self.entity_id,
                'state': self.state,
                'attributes': self.attributes,
                'last_changed': util.datetime_to_str(self.last_changed)}

    @classmethod
    def from_dict(cls, json_dict):
        """ Static method to create a state from a dict.
        Ensures: state == State.from_json_dict(state.to_json_dict()) """

        if not (json_dict and
                'entity_id' in json_dict and
                'state' in json_dict):
            return None

        last_changed = json_dict.get('last_changed')

        if last_changed:
            last_changed = util.str_to_datetime(last_changed)

        return cls(json_dict['entity_id'], json_dict['state'],
                   json_dict.get('attributes'), last_changed)

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and
                self.state == other.state and
                self.attributes == other.attributes)

    def __repr__(self):
        if self.attributes:
            return "<state {}:{} @ {}>".format(
                self.state, util.repr_helper(self.attributes),
                util.datetime_to_str(self.last_changed))
        else:
            return "<state {} @ {}>".format(
                self.state, util.datetime_to_str(self.last_changed))


class StateMachine(object):
    """ Helper class that tracks the state of different entities. """

    def __init__(self, bus):
        self._states = {}
        self._bus = bus
        self._lock = threading.Lock()

    @property
    def entity_ids(self):
        """ List of entity ids that are being tracked. """
        return list(self._states.keys())

    def all(self):
        """ Returns a list of all states. """
        return [state.copy() for state in self._states.values()]

    def get(self, entity_id):
        """ Returns the state of the specified entity. """
        state = self._states.get(entity_id)

        # Make a copy so people won't mutate the state
        return state.copy() if state else None

    def is_state(self, entity_id, state):
        """ Returns True if entity exists and is specified state. """
        return (entity_id in self._states and
                self._states[entity_id].state == state)

    def remove(self, entity_id):
        """ Removes a entity from the state machine.

        Returns boolean to indicate if a entity was removed. """
        with self._lock:
            return self._states.pop(entity_id, None) is not None

    def set(self, entity_id, new_state, attributes=None):
        """ Set the state of an entity, add entity if it does not exist.

        Attributes is an optional dict to specify attributes of this state. """

        attributes = attributes or {}

        with self._lock:
            old_state = self._states.get(entity_id)

            # If state did not exist or is different, set it
            if not old_state or \
               old_state.state != new_state or \
               old_state.attributes != attributes:

                state = self._states[entity_id] = \
                    State(entity_id, new_state, attributes)

                event_data = {'entity_id': entity_id, 'new_state': state}

                if old_state:
                    event_data['old_state'] = old_state

                self._bus.fire(EVENT_STATE_CHANGED, event_data)


# pylint: disable=too-few-public-methods
class ServiceCall(object):
    """ Represents a call to a service. """

    __slots__ = ['domain', 'service', 'data']

    def __init__(self, domain, service, data=None):
        self.domain = domain
        self.service = service
        self.data = data or {}

    def __repr__(self):
        if self.data:
            return "<ServiceCall {}.{}: {}>".format(
                self.domain, self.service, util.repr_helper(self.data))
        else:
            return "<ServiceCall {}.{}>".format(self.domain, self.service)


class ServiceRegistry(object):
    """ Offers services over the eventbus. """

    def __init__(self, bus, pool=None):
        self._services = {}
        self._lock = threading.Lock()
        self._pool = pool or create_worker_pool()
        bus.listen(EVENT_CALL_SERVICE, self._event_to_service_call)

    @property
    def services(self):
        """ Dict with per domain a list of available services. """
        with self._lock:
            return {domain: list(self._services[domain].keys())
                    for domain in self._services}

    def has_service(self, domain, service):
        """ Returns True if specified service exists. """
        return service in self._services.get(domain, [])

    def register(self, domain, service, service_func):
        """ Register a service. """
        with self._lock:
            if domain in self._services:
                self._services[domain][service] = service_func
            else:
                self._services[domain] = {service: service_func}

    def _event_to_service_call(self, event):
        """ Calls a service from an event. """
        service_data = dict(event.data)
        domain = service_data.pop(ATTR_DOMAIN, None)
        service = service_data.pop(ATTR_SERVICE, None)

        with self._lock:
            if domain in self._services and service in self._services[domain]:
                service_call = ServiceCall(domain, service, service_data)

                self._pool.add_job(JobPriority.EVENT_SERVICE,
                                   (self._services[domain][service],
                                    service_call))


class Timer(threading.Thread):
    """ Timer will sent out an event every TIMER_INTERVAL seconds. """

    def __init__(self, hass, interval=None):
        threading.Thread.__init__(self)

        self.daemon = True
        self._bus = hass.bus
        self.interval = interval or TIMER_INTERVAL
        self._stop = threading.Event()

        # We want to be able to fire every time a minute starts (seconds=0).
        # We want this so other modules can use that to make sure they fire
        # every minute.
        assert 60 % self.interval == 0, "60 % TIMER_INTERVAL should be 0!"

        hass.listen_once_event(EVENT_HOMEASSISTANT_START,
                               lambda event: self.start())

        hass.listen_once_event(EVENT_HOMEASSISTANT_STOP,
                               lambda event: self._stop.set())

    def run(self):
        """ Start the timer. """

        _LOGGER.info("Timer:starting")

        last_fired_on_second = -1

        calc_now = dt.datetime.now
        interval = self.interval

        while not self._stop.isSet():
            now = calc_now()

            # First check checks if we are not on a second matching the
            # timer interval. Second check checks if we did not already fire
            # this interval.
            if now.second % interval or \
               now.second == last_fired_on_second:

                # Sleep till it is the next time that we have to fire an event.
                # Aim for halfway through the second that fits TIMER_INTERVAL.
                # If TIMER_INTERVAL is 10 fire at .5, 10.5, 20.5, etc seconds.
                # This will yield the best results because time.sleep() is not
                # 100% accurate because of non-realtime OS's
                slp_seconds = interval - now.second % interval + \
                    .5 - now.microsecond/1000000.0

                time.sleep(slp_seconds)

                now = calc_now()

            last_fired_on_second = now.second

            self._bus.fire(EVENT_TIME_CHANGED, {ATTR_NOW: now})


class HomeAssistantError(Exception):
    """ General Home Assistant exception occured. """
    pass


class InvalidEntityFormatError(HomeAssistantError):
    """ When an invalid formatted entity is encountered. """
    pass


class NoEntitySpecifiedError(HomeAssistantError):
    """ When no entity is specified. """
    pass
