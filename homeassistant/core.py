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
import functools as ft
from collections import namedtuple

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    SERVICE_HOMEASSISTANT_STOP, EVENT_TIME_CHANGED, EVENT_STATE_CHANGED,
    EVENT_CALL_SERVICE, ATTR_NOW, ATTR_DOMAIN, ATTR_SERVICE, MATCH_ALL,
    EVENT_SERVICE_EXECUTED, ATTR_SERVICE_CALL_ID, EVENT_SERVICE_REGISTERED,
    TEMP_CELCIUS, TEMP_FAHRENHEIT, ATTR_FRIENDLY_NAME)
from homeassistant.exceptions import (
    HomeAssistantError, InvalidEntityFormatError)
import homeassistant.util as util
import homeassistant.util.dt as date_util
import homeassistant.helpers.temperature as temp_helper
from homeassistant.config import get_default_config_dir

DOMAIN = "homeassistant"

# How often time_changed event should fire
TIMER_INTERVAL = 1  # seconds

# How long we wait for the result of a service call
SERVICE_CALL_LIMIT = 10  # seconds

# Define number of MINIMUM worker threads.
# During bootstrap of HA (see bootstrap._setup_component()) worker threads
# will be added for each component that polls devices.
MIN_WORKER_THREAD = 2

# Pattern for validating entity IDs (format: <domain>.<entity>)
ENTITY_ID_PATTERN = re.compile(r"^(?P<domain>\w+)\.(?P<entity>\w+)$")

_LOGGER = logging.getLogger(__name__)

# Temporary to support deprecated methods
_MockHA = namedtuple("MockHomeAssistant", ['bus'])


class HomeAssistant(object):
    """ Core class to route all communication to right components. """

    def __init__(self):
        self.pool = pool = create_worker_pool()
        self.bus = EventBus(pool)
        self.services = ServiceRegistry(self.bus, pool)
        self.states = StateMachine(self.bus)
        self.config = Config()

    def start(self):
        """ Start home assistant. """
        _LOGGER.info(
            "Starting Home Assistant (%d threads)", self.pool.worker_count)

        create_timer(self)
        self.bus.fire(EVENT_HOMEASSISTANT_START)

    def block_till_stopped(self):
        """ Will register service homeassistant/stop and
            will block until called. """
        request_shutdown = threading.Event()

        def stop_homeassistant(service):
            """ Stops Home Assistant. """
            request_shutdown.set()

        self.services.register(
            DOMAIN, SERVICE_HOMEASSISTANT_STOP, stop_homeassistant)

        while not request_shutdown.isSet():
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break

        self.stop()

    def stop(self):
        """ Stops Home Assistant and shuts down all threads. """
        _LOGGER.info("Stopping")

        self.bus.fire(EVENT_HOMEASSISTANT_STOP)

        # Wait till all responses to homeassistant_stop are done
        self.pool.block_till_done()

        self.pool.stop()

    def track_point_in_time(self, action, point_in_time):
        """Deprecated method as of 8/4/2015 to track point in time."""
        _LOGGER.warning(
            'hass.track_point_in_time is deprecated. '
            'Please use homeassistant.helpers.event.track_point_in_time')
        import homeassistant.helpers.event as helper
        helper.track_point_in_time(self, action, point_in_time)

    def track_point_in_utc_time(self, action, point_in_time):
        """Deprecated method as of 8/4/2015 to track point in UTC time."""
        _LOGGER.warning(
            'hass.track_point_in_utc_time is deprecated. '
            'Please use homeassistant.helpers.event.track_point_in_utc_time')
        import homeassistant.helpers.event as helper
        helper.track_point_in_utc_time(self, action, point_in_time)

    def track_utc_time_change(self, action,
                              year=None, month=None, day=None,
                              hour=None, minute=None, second=None):
        """Deprecated method as of 8/4/2015 to track UTC time change."""
        # pylint: disable=too-many-arguments
        _LOGGER.warning(
            'hass.track_utc_time_change is deprecated. '
            'Please use homeassistant.helpers.event.track_utc_time_change')
        import homeassistant.helpers.event as helper
        helper.track_utc_time_change(self, action, year, month, day, hour,
                                     minute, second)

    def track_time_change(self, action,
                          year=None, month=None, day=None,
                          hour=None, minute=None, second=None, utc=False):
        """Deprecated method as of 8/4/2015 to track time change."""
        # pylint: disable=too-many-arguments
        _LOGGER.warning(
            'hass.track_time_change is deprecated. '
            'Please use homeassistant.helpers.event.track_time_change')
        import homeassistant.helpers.event as helper
        helper.track_time_change(self, action, year, month, day, hour,
                                 minute, second)


class JobPriority(util.OrderedEnum):
    """ Provides priorities for bus events. """
    # pylint: disable=no-init,too-few-public-methods

    EVENT_CALLBACK = 0
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
        elif event_type == EVENT_SERVICE_EXECUTED:
            return JobPriority.EVENT_CALLBACK
        else:
            return JobPriority.EVENT_DEFAULT


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

    __slots__ = ['event_type', 'data', 'origin', 'time_fired']

    def __init__(self, event_type, data=None, origin=EventOrigin.local,
                 time_fired=None):
        self.event_type = event_type
        self.data = data or {}
        self.origin = origin
        self.time_fired = date_util.strip_microseconds(
            time_fired or date_util.utcnow())

    def as_dict(self):
        """ Returns a dict representation of this Event. """
        return {
            'event_type': self.event_type,
            'data': dict(self.data),
            'origin': str(self.origin),
            'time_fired': date_util.datetime_to_str(self.time_fired),
        }

    def __repr__(self):
        # pylint: disable=maybe-no-member
        if self.data:
            return "<Event {}[{}]: {}>".format(
                self.event_type, str(self.origin)[0],
                util.repr_helper(self.data))
        else:
            return "<Event {}[{}]>".format(self.event_type,
                                           str(self.origin)[0])

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and
                self.event_type == other.event_type and
                self.data == other.data and
                self.origin == other.origin and
                self.time_fired == other.time_fired)


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
        if not self._pool.running:
            raise HomeAssistantError('Home Assistant has shut down.')

        with self._lock:
            # Copy the list of the current listeners because some listeners
            # remove themselves as a listener while being executed which
            # causes the iterator to be confused.
            get = self._listeners.get
            listeners = get(MATCH_ALL, []) + get(event_type, [])

            event = Event(event_type, event_data, origin)

            if event_type != EVENT_TIME_CHANGED:
                _LOGGER.info("Bus:Handling %s", event)

            if not listeners:
                return

            job_priority = JobPriority.from_event_type(event_type)

            for func in listeners:
                self._pool.add_job(job_priority, (func, event))

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

    def listen_once(self, event_type, listener):
        """ Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Returns registered listener that can be used with remove_listener.
        """
        @ft.wraps(listener)
        def onetime_listener(event):
            """ Removes listener from eventbus and then fires listener. """
            if hasattr(onetime_listener, 'run'):
                return
            # Set variable so that we will never run twice.
            # Because the event bus might have to wait till a thread comes
            # available to execute this listener it might occur that the
            # listener gets lined up twice to be executed.
            # This will make sure the second time it does nothing.
            onetime_listener.run = True

            self.remove_listener(event_type, onetime_listener)

            listener(event)

        self.listen(event_type, onetime_listener)

        return onetime_listener

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
    """
    Object to represent a state within the state machine.

    entity_id: the entity that is represented.
    state: the state of the entity
    attributes: extra information on entity and state
    last_changed: last time the state was changed, not the attributes.
    last_updated: last time this object was updated.
    """

    __slots__ = ['entity_id', 'state', 'attributes',
                 'last_changed', 'last_updated']

    # pylint: disable=too-many-arguments
    def __init__(self, entity_id, state, attributes=None, last_changed=None,
                 last_updated=None):
        if not ENTITY_ID_PATTERN.match(entity_id):
            raise InvalidEntityFormatError((
                "Invalid entity id encountered: {}. "
                "Format should be <domain>.<object_id>").format(entity_id))

        self.entity_id = entity_id.lower()
        self.state = state
        self.attributes = attributes or {}
        self.last_updated = date_util.strip_microseconds(
            last_updated or date_util.utcnow())

        # Strip microsecond from last_changed else we cannot guarantee
        # state == State.from_dict(state.as_dict())
        # This behavior occurs because to_dict uses datetime_to_str
        # which does not preserve microseconds
        self.last_changed = date_util.strip_microseconds(
            last_changed or self.last_updated)

    @property
    def domain(self):
        """ Returns domain of this state. """
        return util.split_entity_id(self.entity_id)[0]

    @property
    def object_id(self):
        """ Returns object_id of this state. """
        return util.split_entity_id(self.entity_id)[1]

    @property
    def name(self):
        """ Name to represent this state. """
        return (
            self.attributes.get(ATTR_FRIENDLY_NAME) or
            self.object_id.replace('_', ' '))

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
                'last_changed': date_util.datetime_to_str(self.last_changed),
                'last_updated': date_util.datetime_to_str(self.last_updated)}

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
            last_changed = date_util.str_to_datetime(last_changed)

        last_updated = json_dict.get('last_updated')

        if last_updated:
            last_updated = date_util.str_to_datetime(last_updated)

        return cls(json_dict['entity_id'], json_dict['state'],
                   json_dict.get('attributes'), last_changed, last_updated)

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and
                self.entity_id == other.entity_id and
                self.state == other.state and
                self.attributes == other.attributes)

    def __repr__(self):
        attr = "; {}".format(util.repr_helper(self.attributes)) \
               if self.attributes else ""

        return "<state {}={}{} @ {}>".format(
            self.entity_id, self.state, attr,
            date_util.datetime_to_local_str(self.last_changed))


class StateMachine(object):
    """ Helper class that tracks the state of different entities. """

    def __init__(self, bus):
        self._states = {}
        self._bus = bus
        self._lock = threading.Lock()

    def entity_ids(self, domain_filter=None):
        """ List of entity ids that are being tracked. """
        if domain_filter is None:
            return list(self._states.keys())

        domain_filter = domain_filter.lower()

        return [state.entity_id for key, state
                in self._states.items()
                if util.split_entity_id(key)[0] == domain_filter]

    def all(self):
        """ Returns a list of all states. """
        with self._lock:
            return [state.copy() for state in self._states.values()]

    def get(self, entity_id):
        """ Returns the state of the specified entity. """
        state = self._states.get(entity_id.lower())

        # Make a copy so people won't mutate the state
        return state.copy() if state else None

    def is_state(self, entity_id, state):
        """ Returns True if entity exists and is specified state. """
        entity_id = entity_id.lower()

        return (entity_id in self._states and
                self._states[entity_id].state == state)

    def remove(self, entity_id):
        """ Removes an entity from the state machine.

        Returns boolean to indicate if an entity was removed. """
        entity_id = entity_id.lower()

        with self._lock:
            return self._states.pop(entity_id, None) is not None

    def set(self, entity_id, new_state, attributes=None):
        """ Set the state of an entity, add entity if it does not exist.

        Attributes is an optional dict to specify attributes of this state.

        If you just update the attributes and not the state, last changed will
        not be affected.
        """
        entity_id = entity_id.lower()
        new_state = str(new_state)
        attributes = attributes or {}

        with self._lock:
            old_state = self._states.get(entity_id)

            is_existing = old_state is not None
            same_state = is_existing and old_state.state == new_state
            same_attr = is_existing and old_state.attributes == attributes

            if same_state and same_attr:
                return

            # If state did not exist or is different, set it
            last_changed = old_state.last_changed if same_state else None

            state = State(entity_id, new_state, attributes, last_changed)
            self._states[entity_id] = state

            event_data = {'entity_id': entity_id, 'new_state': state}

            if old_state:
                event_data['old_state'] = old_state

            self._bus.fire(EVENT_STATE_CHANGED, event_data)

    def track_change(self, entity_ids, action, from_state=None, to_state=None):
        """
        DEPRECATED AS OF 8/4/2015
        """
        _LOGGER.warning(
            'hass.states.track_change is deprecated. '
            'Use homeassistant.helpers.event.track_state_change instead.')
        import homeassistant.helpers.event as helper
        helper.track_state_change(_MockHA(self._bus), entity_ids, action,
                                  from_state, to_state)


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
        self._bus = bus
        self._cur_id = 0
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

            self._bus.fire(
                EVENT_SERVICE_REGISTERED,
                {ATTR_DOMAIN: domain, ATTR_SERVICE: service})

    def call(self, domain, service, service_data=None, blocking=False):
        """
        Calls specified service.
        Specify blocking=True to wait till service is executed.
        Waits a maximum of SERVICE_CALL_LIMIT.

        If blocking = True, will return boolean if service executed
        succesfully within SERVICE_CALL_LIMIT.

        This method will fire an event to call the service.
        This event will be picked up by this ServiceRegistry and any
        other ServiceRegistry that is listening on the EventBus.

        Because the service is sent as an event you are not allowed to use
        the keys ATTR_DOMAIN and ATTR_SERVICE in your service_data.
        """
        call_id = self._generate_unique_id()
        event_data = service_data or {}
        event_data[ATTR_DOMAIN] = domain
        event_data[ATTR_SERVICE] = service
        event_data[ATTR_SERVICE_CALL_ID] = call_id

        if blocking:
            executed_event = threading.Event()

            def service_executed(call):
                """
                Called when a service is executed.
                Will set the event if matches our service call.
                """
                if call.data[ATTR_SERVICE_CALL_ID] == call_id:
                    executed_event.set()

            self._bus.listen(EVENT_SERVICE_EXECUTED, service_executed)

        self._bus.fire(EVENT_CALL_SERVICE, event_data)

        if blocking:
            success = executed_event.wait(SERVICE_CALL_LIMIT)
            self._bus.remove_listener(
                EVENT_SERVICE_EXECUTED, service_executed)
            return success

    def _event_to_service_call(self, event):
        """ Calls a service from an event. """
        service_data = dict(event.data)
        domain = service_data.pop(ATTR_DOMAIN, None)
        service = service_data.pop(ATTR_SERVICE, None)

        if not self.has_service(domain, service):
            return

        service_handler = self._services[domain][service]
        service_call = ServiceCall(domain, service, service_data)

        # Add a job to the pool that calls _execute_service
        self._pool.add_job(JobPriority.EVENT_SERVICE,
                           (self._execute_service,
                            (service_handler, service_call)))

    def _execute_service(self, service_and_call):
        """ Executes a service and fires a SERVICE_EXECUTED event. """
        service, call = service_and_call
        service(call)

        if ATTR_SERVICE_CALL_ID in call.data:
            self._bus.fire(
                EVENT_SERVICE_EXECUTED,
                {ATTR_SERVICE_CALL_ID: call.data[ATTR_SERVICE_CALL_ID]})

    def _generate_unique_id(self):
        """ Generates a unique service call id. """
        self._cur_id += 1
        return "{}-{}".format(id(self), self._cur_id)


class Config(object):
    """ Configuration settings for Home Assistant. """

    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        self.latitude = None
        self.longitude = None
        self.temperature_unit = None
        self.location_name = None
        self.time_zone = None

        # List of loaded components
        self.components = []

        # Remote.API object pointing at local API
        self.api = None

        # Directory that holds the configuration
        self.config_dir = get_default_config_dir()

    def path(self, *path):
        """ Returns path to the file within the config dir. """
        return os.path.join(self.config_dir, *path)

    def temperature(self, value, unit):
        """ Converts temperature to user preferred unit if set. """
        if not (unit in (TEMP_CELCIUS, TEMP_FAHRENHEIT) and
                self.temperature_unit and unit != self.temperature_unit):
            return value, unit

        try:
            temp = float(value)
        except ValueError:  # Could not convert value to float
            return value, unit

        return (
            round(temp_helper.convert(temp, unit, self.temperature_unit), 1),
            self.temperature_unit)

    def as_dict(self):
        """ Converts config to a dictionary. """
        time_zone = self.time_zone or date_util.UTC

        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'temperature_unit': self.temperature_unit,
            'location_name': self.location_name,
            'time_zone': time_zone.zone,
            'components': self.components,
        }


def create_timer(hass, interval=TIMER_INTERVAL):
    """ Creates a timer. Timer will start on HOMEASSISTANT_START. """
    # We want to be able to fire every time a minute starts (seconds=0).
    # We want this so other modules can use that to make sure they fire
    # every minute.
    assert 60 % interval == 0, "60 % TIMER_INTERVAL should be 0!"

    def timer():
        """Send an EVENT_TIME_CHANGED on interval."""
        stop_event = threading.Event()

        def stop_timer(event):
            """Stop the timer."""
            stop_event.set()

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_timer)

        _LOGGER.info("Timer:starting")

        last_fired_on_second = -1

        calc_now = date_util.utcnow

        while not stop_event.isSet():
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

            # Event might have been set while sleeping
            if not stop_event.isSet():
                try:
                    hass.bus.fire(EVENT_TIME_CHANGED, {ATTR_NOW: now})
                except HomeAssistantError:
                    # HA raises error if firing event after it has shut down
                    break

    def start_timer(event):
        """Start the timer."""
        thread = threading.Thread(target=timer)
        thread.daemon = True
        thread.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_timer)


def create_worker_pool(worker_count=MIN_WORKER_THREAD):
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

    def busy_callback(worker_count, current_jobs, pending_jobs_count):
        """ Callback to be called when the pool queue gets too big. """

        _LOGGER.warning(
            "WorkerPool:All %d threads are busy and %d jobs pending",
            worker_count, pending_jobs_count)

        for start, job in current_jobs:
            _LOGGER.warning("WorkerPool:Current job from %s: %s",
                            date_util.datetime_to_local_str(start), job)

    return util.ThreadPool(job_handler, worker_count, busy_callback)
