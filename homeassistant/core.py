"""
Core components of Home Assistant.

Home Assistant is a Home Automation framework for observing the state
of entities and react to changes.
"""
# pylint: disable=unused-import, too-many-lines
import asyncio
from concurrent.futures import ThreadPoolExecutor
import enum
import logging
import os
import pathlib
import re
import sys
import threading
from time import monotonic

from types import MappingProxyType
from typing import Optional, Any, Callable, List  # NOQA

from async_timeout import timeout
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import (
    ATTR_DOMAIN, ATTR_FRIENDLY_NAME, ATTR_NOW, ATTR_SERVICE,
    ATTR_SERVICE_CALL_ID, ATTR_SERVICE_DATA, EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    EVENT_SERVICE_EXECUTED, EVENT_SERVICE_REGISTERED, EVENT_STATE_CHANGED,
    EVENT_TIME_CHANGED, MATCH_ALL, EVENT_HOMEASSISTANT_CLOSE,
    EVENT_SERVICE_REMOVED, __version__)
from homeassistant import loader
from homeassistant.exceptions import (
    HomeAssistantError, InvalidEntityFormatError, InvalidStateError)
from homeassistant.util.async import (
    run_coroutine_threadsafe, run_callback_threadsafe,
    fire_coroutine_threadsafe)
import homeassistant.util as util
import homeassistant.util.dt as dt_util
import homeassistant.util.location as location
from homeassistant.util.unit_system import UnitSystem, METRIC_SYSTEM  # NOQA

DOMAIN = 'homeassistant'

# How long we wait for the result of a service call
SERVICE_CALL_LIMIT = 10  # seconds

# Pattern for validating entity IDs (format: <domain>.<entity>)
ENTITY_ID_PATTERN = re.compile(r"^(\w+)\.(\w+)$")

# How long to wait till things that run on startup have to finish.
TIMEOUT_EVENT_START = 15

_LOGGER = logging.getLogger(__name__)


def split_entity_id(entity_id: str) -> List[str]:
    """Split a state entity_id into domain, object_id."""
    return entity_id.split(".", 1)


def valid_entity_id(entity_id: str) -> bool:
    """Test if an entity ID is a valid format."""
    return ENTITY_ID_PATTERN.match(entity_id) is not None


def valid_state(state: str) -> bool:
    """Test if a state is valid."""
    return len(state) < 256


def callback(func: Callable[..., None]) -> Callable[..., None]:
    """Annotation to mark method as safe to call from within the event loop."""
    # pylint: disable=protected-access
    func._hass_callback = True
    return func


def is_callback(func: Callable[..., Any]) -> bool:
    """Check if function is safe to be called in the event loop."""
    return '_hass_callback' in func.__dict__


@callback
def async_loop_exception_handler(loop, context):
    """Handle all exception inside the core loop."""
    kwargs = {}
    exception = context.get('exception')
    if exception:
        kwargs['exc_info'] = (type(exception), exception,
                              exception.__traceback__)

    _LOGGER.error("Error doing job: %s", context['message'], **kwargs)


class CoreState(enum.Enum):
    """Represent the current state of Home Assistant."""

    not_running = 'NOT_RUNNING'
    starting = 'STARTING'
    running = 'RUNNING'
    stopping = 'STOPPING'

    def __str__(self) -> str:
        """Return the event."""
        return self.value


class HomeAssistant(object):
    """Root object of the Home Assistant home automation."""

    def __init__(self, loop=None):
        """Initialize new Home Assistant object."""
        if sys.platform == 'win32':
            self.loop = loop or asyncio.ProactorEventLoop()
        else:
            self.loop = loop or asyncio.get_event_loop()

        executor_opts = {'max_workers': 10}
        if sys.version_info[:2] >= (3, 5):
            # It will default set to the number of processors on the machine,
            # multiplied by 5. That is better for overlap I/O workers.
            executor_opts['max_workers'] = None
        if sys.version_info[:2] >= (3, 6):
            executor_opts['thread_name_prefix'] = 'SyncWorker'

        self.executor = ThreadPoolExecutor(**executor_opts)
        self.loop.set_default_executor(self.executor)
        self.loop.set_exception_handler(async_loop_exception_handler)
        self._pending_tasks = []
        self._track_task = True
        self.bus = EventBus(self)
        self.services = ServiceRegistry(self)
        self.states = StateMachine(self.bus, self.loop)
        self.config = Config()  # type: Config
        self.components = loader.Components(self)
        self.helpers = loader.Helpers(self)
        # This is a dictionary that any component can store any data on.
        self.data = {}
        self.state = CoreState.not_running
        self.exit_code = None

    @property
    def is_running(self) -> bool:
        """Return if Home Assistant is running."""
        return self.state in (CoreState.starting, CoreState.running)

    def start(self) -> None:
        """Start home assistant."""
        # Register the async start
        fire_coroutine_threadsafe(self.async_start(), self.loop)

        # Run forever and catch keyboard interrupt
        try:
            # Block until stopped
            _LOGGER.info("Starting Home Assistant core loop")
            self.loop.run_forever()
            return self.exit_code
        except KeyboardInterrupt:
            self.loop.call_soon_threadsafe(
                self.loop.create_task, self.async_stop())
            self.loop.run_forever()
        finally:
            self.loop.close()

    @asyncio.coroutine
    def async_start(self):
        """Finalize startup from inside the event loop.

        This method is a coroutine.
        """
        _LOGGER.info("Starting Home Assistant")
        self.state = CoreState.starting

        # pylint: disable=protected-access
        self.loop._thread_ident = threading.get_ident()
        self.bus.async_fire(EVENT_HOMEASSISTANT_START)

        try:
            # Only block for EVENT_HOMEASSISTANT_START listener
            self.async_stop_track_tasks()
            with timeout(TIMEOUT_EVENT_START, loop=self.loop):
                yield from self.async_block_till_done()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                'Something is blocking Home Assistant from wrapping up the '
                'start up phase. We\'re going to continue anyway. Please '
                'report the following info at http://bit.ly/2ogP58T : %s',
                ', '.join(self.config.components))

        # Allow automations to set up the start triggers before changing state
        yield from asyncio.sleep(0, loop=self.loop)
        self.state = CoreState.running
        _async_create_timer(self)

    def add_job(self, target: Callable[..., None], *args: Any) -> None:
        """Add job to the executor pool.

        target: target to call.
        args: parameters for method to call.
        """
        if target is None:
            raise ValueError("Don't call add_job with None")
        self.loop.call_soon_threadsafe(self.async_add_job, target, *args)

    @callback
    def async_add_job(self, target: Callable[..., None], *args: Any) -> None:
        """Add a job from within the eventloop.

        This method must be run in the event loop.

        target: target to call.
        args: parameters for method to call.
        """
        task = None

        if asyncio.iscoroutine(target):
            task = self.loop.create_task(target)
        elif is_callback(target):
            self.loop.call_soon(target, *args)
        elif asyncio.iscoroutinefunction(target):
            task = self.loop.create_task(target(*args))
        else:
            task = self.loop.run_in_executor(None, target, *args)

        # If a task is scheduled
        if self._track_task and task is not None:
            self._pending_tasks.append(task)

        return task

    @callback
    def async_track_tasks(self):
        """Track tasks so you can wait for all tasks to be done."""
        self._track_task = True

    @callback
    def async_stop_track_tasks(self):
        """Stop track tasks so you can't wait for all tasks to be done."""
        self._track_task = False

    @callback
    def async_run_job(self, target: Callable[..., None], *args: Any) -> None:
        """Run a job from within the event loop.

        This method must be run in the event loop.

        target: target to call.
        args: parameters for method to call.
        """
        if not asyncio.iscoroutine(target) and is_callback(target):
            target(*args)
        else:
            self.async_add_job(target, *args)

    def block_till_done(self) -> None:
        """Block till all pending work is done."""
        run_coroutine_threadsafe(
            self.async_block_till_done(), loop=self.loop).result()

    @asyncio.coroutine
    def async_block_till_done(self):
        """Block till all pending work is done."""
        # To flush out any call_soon_threadsafe
        yield from asyncio.sleep(0, loop=self.loop)

        while self._pending_tasks:
            pending = [task for task in self._pending_tasks
                       if not task.done()]
            self._pending_tasks.clear()
            if pending:
                yield from asyncio.wait(pending, loop=self.loop)
            else:
                yield from asyncio.sleep(0, loop=self.loop)

    def stop(self) -> None:
        """Stop Home Assistant and shuts down all threads."""
        fire_coroutine_threadsafe(self.async_stop(), self.loop)

    @asyncio.coroutine
    def async_stop(self, exit_code=0) -> None:
        """Stop Home Assistant and shuts down all threads.

        This method is a coroutine.
        """
        # stage 1
        self.state = CoreState.stopping
        self.async_track_tasks()
        self.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        yield from self.async_block_till_done()

        # stage 2
        self.state = CoreState.not_running
        self.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
        yield from self.async_block_till_done()
        self.executor.shutdown()

        self.exit_code = exit_code
        self.loop.stop()


class EventOrigin(enum.Enum):
    """Represent the origin of an event."""

    local = 'LOCAL'
    remote = 'REMOTE'

    def __str__(self):
        """Return the event."""
        return self.value


class Event(object):
    """Representation of an event within the bus."""

    __slots__ = ['event_type', 'data', 'origin', 'time_fired']

    def __init__(self, event_type, data=None, origin=EventOrigin.local,
                 time_fired=None):
        """Initialize a new event."""
        self.event_type = event_type
        self.data = data or {}
        self.origin = origin
        self.time_fired = time_fired or dt_util.utcnow()

    def as_dict(self):
        """Create a dict representation of this Event.

        Async friendly.
        """
        return {
            'event_type': self.event_type,
            'data': dict(self.data),
            'origin': str(self.origin),
            'time_fired': self.time_fired,
        }

    def __repr__(self):
        """Return the representation."""
        # pylint: disable=maybe-no-member
        if self.data:
            return "<Event {}[{}]: {}>".format(
                self.event_type, str(self.origin)[0],
                util.repr_helper(self.data))

        return "<Event {}[{}]>".format(self.event_type,
                                       str(self.origin)[0])

    def __eq__(self, other):
        """Return the comparison."""
        return (self.__class__ == other.__class__ and
                self.event_type == other.event_type and
                self.data == other.data and
                self.origin == other.origin and
                self.time_fired == other.time_fired)


class EventBus(object):
    """Allow the firing of and listening for events."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a new event bus."""
        self._listeners = {}
        self._hass = hass

    @callback
    def async_listeners(self):
        """Return dictionary with events and the number of listeners.

        This method must be run in the event loop.
        """
        return {key: len(self._listeners[key])
                for key in self._listeners}

    @property
    def listeners(self):
        """Return dictionary with events and the number of listeners."""
        return run_callback_threadsafe(
            self._hass.loop, self.async_listeners
        ).result()

    def fire(self, event_type: str, event_data=None, origin=EventOrigin.local):
        """Fire an event."""
        self._hass.loop.call_soon_threadsafe(
            self.async_fire, event_type, event_data, origin)

    @callback
    def async_fire(self, event_type: str, event_data=None,
                   origin=EventOrigin.local):
        """Fire an event.

        This method must be run in the event loop.
        """
        listeners = self._listeners.get(event_type, [])

        # EVENT_HOMEASSISTANT_CLOSE should go only to his listeners
        match_all_listeners = self._listeners.get(MATCH_ALL)
        if (match_all_listeners is not None and
                event_type != EVENT_HOMEASSISTANT_CLOSE):
            listeners = match_all_listeners + listeners

        event = Event(event_type, event_data, origin)

        if event_type != EVENT_TIME_CHANGED:
            _LOGGER.info("Bus:Handling %s", event)

        if not listeners:
            return

        for func in listeners:
            self._hass.async_add_job(func, event)

    def listen(self, event_type, listener):
        """Listen for all events or events of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.
        """
        async_remove_listener = run_callback_threadsafe(
            self._hass.loop, self.async_listen, event_type, listener).result()

        def remove_listener():
            """Remove the listener."""
            run_callback_threadsafe(
                self._hass.loop, async_remove_listener).result()

        return remove_listener

    @callback
    def async_listen(self, event_type, listener):
        """Listen for all events or events of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        This method must be run in the event loop.
        """
        if event_type in self._listeners:
            self._listeners[event_type].append(listener)
        else:
            self._listeners[event_type] = [listener]

        def remove_listener():
            """Remove the listener."""
            self._async_remove_listener(event_type, listener)

        return remove_listener

    def listen_once(self, event_type, listener):
        """Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Returns function to unsubscribe the listener.
        """
        async_remove_listener = run_callback_threadsafe(
            self._hass.loop, self.async_listen_once, event_type, listener,
        ).result()

        def remove_listener():
            """Remove the listener."""
            run_callback_threadsafe(
                self._hass.loop, async_remove_listener).result()

        return remove_listener

    @callback
    def async_listen_once(self, event_type, listener):
        """Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Returns registered listener that can be used with remove_listener.

        This method must be run in the event loop.
        """
        @callback
        def onetime_listener(event):
            """Remove listener from eventbus and then fire listener."""
            if hasattr(onetime_listener, 'run'):
                return
            # Set variable so that we will never run twice.
            # Because the event bus loop might have async_fire queued multiple
            # times, its possible this listener may already be lined up
            # multiple times as well.
            # This will make sure the second time it does nothing.
            setattr(onetime_listener, 'run', True)
            self._async_remove_listener(event_type, onetime_listener)
            self._hass.async_run_job(listener, event)

        return self.async_listen(event_type, onetime_listener)

    @callback
    def _async_remove_listener(self, event_type, listener):
        """Remove a listener of a specific event_type.

        This method must be run in the event loop.
        """
        try:
            self._listeners[event_type].remove(listener)

            # delete event_type list if empty
            if not self._listeners[event_type]:
                self._listeners.pop(event_type)
        except (KeyError, ValueError):
            # KeyError is key event_type listener did not exist
            # ValueError if listener did not exist within event_type
            _LOGGER.warning("Unable to remove unknown listener %s", listener)


class State(object):
    """Object to represent a state within the state machine.

    entity_id: the entity that is represented.
    state: the state of the entity
    attributes: extra information on entity and state
    last_changed: last time the state was changed, not the attributes.
    last_updated: last time this object was updated.
    """

    __slots__ = ['entity_id', 'state', 'attributes',
                 'last_changed', 'last_updated']

    def __init__(self, entity_id, state, attributes=None, last_changed=None,
                 last_updated=None):
        """Initialize a new state."""
        state = str(state)

        if not valid_entity_id(entity_id):
            raise InvalidEntityFormatError((
                "Invalid entity id encountered: {}. "
                "Format should be <domain>.<object_id>").format(entity_id))

        if not valid_state(state):
            raise InvalidStateError((
                "Invalid state encountered for entity id: {}. "
                "State max length is 255 characters.").format(entity_id))

        self.entity_id = entity_id.lower()
        self.state = state
        self.attributes = MappingProxyType(attributes or {})
        self.last_updated = last_updated or dt_util.utcnow()
        self.last_changed = last_changed or self.last_updated

    @property
    def domain(self):
        """Domain of this state."""
        return split_entity_id(self.entity_id)[0]

    @property
    def object_id(self):
        """Object id of this state."""
        return split_entity_id(self.entity_id)[1]

    @property
    def name(self):
        """Name of this state."""
        return (
            self.attributes.get(ATTR_FRIENDLY_NAME) or
            self.object_id.replace('_', ' '))

    def as_dict(self):
        """Return a dict representation of the State.

        Async friendly.

        To be used for JSON serialization.
        Ensures: state == State.from_dict(state.as_dict())
        """
        return {'entity_id': self.entity_id,
                'state': self.state,
                'attributes': dict(self.attributes),
                'last_changed': self.last_changed,
                'last_updated': self.last_updated}

    @classmethod
    def from_dict(cls, json_dict):
        """Initialize a state from a dict.

        Async friendly.

        Ensures: state == State.from_json_dict(state.to_json_dict())
        """
        if not (json_dict and 'entity_id' in json_dict and
                'state' in json_dict):
            return None

        last_changed = json_dict.get('last_changed')

        if isinstance(last_changed, str):
            last_changed = dt_util.parse_datetime(last_changed)

        last_updated = json_dict.get('last_updated')

        if isinstance(last_updated, str):
            last_updated = dt_util.parse_datetime(last_updated)

        return cls(json_dict['entity_id'], json_dict['state'],
                   json_dict.get('attributes'), last_changed, last_updated)

    def __eq__(self, other):
        """Return the comparison of the state."""
        return (self.__class__ == other.__class__ and
                self.entity_id == other.entity_id and
                self.state == other.state and
                self.attributes == other.attributes)

    def __repr__(self):
        """Return the representation of the states."""
        attr = "; {}".format(util.repr_helper(self.attributes)) \
               if self.attributes else ""

        return "<state {}={}{} @ {}>".format(
            self.entity_id, self.state, attr,
            dt_util.as_local(self.last_changed).isoformat())


class StateMachine(object):
    """Helper class that tracks the state of different entities."""

    def __init__(self, bus, loop):
        """Initialize state machine."""
        self._states = {}
        self._bus = bus
        self._loop = loop

    def entity_ids(self, domain_filter=None):
        """List of entity ids that are being tracked."""
        future = run_callback_threadsafe(
            self._loop, self.async_entity_ids, domain_filter
        )
        return future.result()

    @callback
    def async_entity_ids(self, domain_filter=None):
        """List of entity ids that are being tracked.

        This method must be run in the event loop.
        """
        if domain_filter is None:
            return list(self._states.keys())

        domain_filter = domain_filter.lower()

        return [state.entity_id for state in self._states.values()
                if state.domain == domain_filter]

    def all(self):
        """Create a list of all states."""
        return run_callback_threadsafe(self._loop, self.async_all).result()

    @callback
    def async_all(self):
        """Create a list of all states.

        This method must be run in the event loop.
        """
        return list(self._states.values())

    def get(self, entity_id):
        """Retrieve state of entity_id or None if not found.

        Async friendly.
        """
        return self._states.get(entity_id.lower())

    def is_state(self, entity_id, state):
        """Test if entity exists and is specified state.

        Async friendly.
        """
        state_obj = self.get(entity_id)
        return state_obj is not None and state_obj.state == state

    def remove(self, entity_id):
        """Remove the state of an entity.

        Returns boolean to indicate if an entity was removed.
        """
        return run_callback_threadsafe(
            self._loop, self.async_remove, entity_id).result()

    @callback
    def async_remove(self, entity_id):
        """Remove the state of an entity.

        Returns boolean to indicate if an entity was removed.

        This method must be run in the event loop.
        """
        entity_id = entity_id.lower()
        old_state = self._states.pop(entity_id, None)

        if old_state is None:
            return False

        self._bus.async_fire(EVENT_STATE_CHANGED, {
            'entity_id': entity_id,
            'old_state': old_state,
            'new_state': None,
        })
        return True

    def set(self, entity_id, new_state, attributes=None, force_update=False):
        """Set the state of an entity, add entity if it does not exist.

        Attributes is an optional dict to specify attributes of this state.

        If you just update the attributes and not the state, last changed will
        not be affected.
        """
        run_callback_threadsafe(
            self._loop,
            self.async_set, entity_id, new_state, attributes, force_update,
        ).result()

    @callback
    def async_set(self, entity_id, new_state, attributes=None,
                  force_update=False):
        """Set the state of an entity, add entity if it does not exist.

        Attributes is an optional dict to specify attributes of this state.

        If you just update the attributes and not the state, last changed will
        not be affected.

        This method must be run in the event loop.
        """
        entity_id = entity_id.lower()
        new_state = str(new_state)
        attributes = attributes or {}
        old_state = self._states.get(entity_id)
        is_existing = old_state is not None
        same_state = (is_existing and old_state.state == new_state and
                      not force_update)
        same_attr = is_existing and old_state.attributes == attributes

        if same_state and same_attr:
            return

        last_changed = old_state.last_changed if same_state else None
        state = State(entity_id, new_state, attributes, last_changed)
        self._states[entity_id] = state
        self._bus.async_fire(EVENT_STATE_CHANGED, {
            'entity_id': entity_id,
            'old_state': old_state,
            'new_state': state,
        })


class Service(object):
    """Representation of a callable service."""

    __slots__ = ['func', 'schema', 'is_callback', 'is_coroutinefunction']

    def __init__(self, func, schema):
        """Initialize a service."""
        self.func = func
        self.schema = schema
        self.is_callback = is_callback(func)
        self.is_coroutinefunction = asyncio.iscoroutinefunction(func)


class ServiceCall(object):
    """Representation of a call to a service."""

    __slots__ = ['domain', 'service', 'data', 'call_id']

    def __init__(self, domain, service, data=None, call_id=None):
        """Initialize a service call."""
        self.domain = domain.lower()
        self.service = service.lower()
        self.data = MappingProxyType(data or {})
        self.call_id = call_id

    def __repr__(self):
        """Return the representation of the service."""
        if self.data:
            return "<ServiceCall {}.{}: {}>".format(
                self.domain, self.service, util.repr_helper(self.data))

        return "<ServiceCall {}.{}>".format(self.domain, self.service)


class ServiceRegistry(object):
    """Offer the services over the eventbus."""

    def __init__(self, hass):
        """Initialize a service registry."""
        self._services = {}
        self._hass = hass
        self._async_unsub_call_event = None

        def _gen_unique_id():
            cur_id = 1
            while True:
                yield '{}-{}'.format(id(self), cur_id)
                cur_id += 1

        gen = _gen_unique_id()
        self._generate_unique_id = lambda: next(gen)

    @property
    def services(self):
        """Return dictionary with per domain a list of available services."""
        return run_callback_threadsafe(
            self._hass.loop, self.async_services,
        ).result()

    @callback
    def async_services(self):
        """Return dictionary with per domain a list of available services.

        This method must be run in the event loop.
        """
        return {domain: self._services[domain].copy()
                for domain in self._services}

    def has_service(self, domain, service):
        """Test if specified service exists.

        Async friendly.
        """
        return service.lower() in self._services.get(domain.lower(), [])

    def register(self, domain, service, service_func, schema=None):
        """
        Register a service.

        Schema is called to coerce and validate the service data.
        """
        run_callback_threadsafe(
            self._hass.loop,
            self.async_register, domain, service, service_func, schema
        ).result()

    @callback
    def async_register(self, domain, service, service_func, schema=None):
        """
        Register a service.

        Schema is called to coerce and validate the service data.

        This method must be run in the event loop.
        """
        domain = domain.lower()
        service = service.lower()
        service_obj = Service(service_func, schema)

        if domain in self._services:
            self._services[domain][service] = service_obj
        else:
            self._services[domain] = {service: service_obj}

        if self._async_unsub_call_event is None:
            self._async_unsub_call_event = self._hass.bus.async_listen(
                EVENT_CALL_SERVICE, self._event_to_service_call)

        self._hass.bus.async_fire(
            EVENT_SERVICE_REGISTERED,
            {ATTR_DOMAIN: domain, ATTR_SERVICE: service}
        )

    def remove(self, domain, service):
        """Remove a registered service from service handler."""
        run_callback_threadsafe(
            self._hass.loop, self.async_remove, domain, service).result()

    @callback
    def async_remove(self, domain, service):
        """Remove a registered service from service handler.

        This method must be run in the event loop.
        """
        domain = domain.lower()
        service = service.lower()

        if service not in self._services.get(domain, {}):
            _LOGGER.warning(
                "Unable to remove unknown service %s/%s.", domain, service)
            return

        self._services[domain].pop(service)

        self._hass.bus.async_fire(
            EVENT_SERVICE_REMOVED,
            {ATTR_DOMAIN: domain, ATTR_SERVICE: service}
        )

    def call(self, domain, service, service_data=None, blocking=False):
        """
        Call a service.

        Specify blocking=True to wait till service is executed.
        Waits a maximum of SERVICE_CALL_LIMIT.

        If blocking = True, will return boolean if service executed
        successfully within SERVICE_CALL_LIMIT.

        This method will fire an event to call the service.
        This event will be picked up by this ServiceRegistry and any
        other ServiceRegistry that is listening on the EventBus.

        Because the service is sent as an event you are not allowed to use
        the keys ATTR_DOMAIN and ATTR_SERVICE in your service_data.
        """
        return run_coroutine_threadsafe(
            self.async_call(domain, service, service_data, blocking),
            self._hass.loop
        ).result()

    @asyncio.coroutine
    def async_call(self, domain, service, service_data=None, blocking=False):
        """
        Call a service.

        Specify blocking=True to wait till service is executed.
        Waits a maximum of SERVICE_CALL_LIMIT.

        If blocking = True, will return boolean if service executed
        successfully within SERVICE_CALL_LIMIT.

        This method will fire an event to call the service.
        This event will be picked up by this ServiceRegistry and any
        other ServiceRegistry that is listening on the EventBus.

        Because the service is sent as an event you are not allowed to use
        the keys ATTR_DOMAIN and ATTR_SERVICE in your service_data.

        This method is a coroutine.
        """
        call_id = self._generate_unique_id()

        event_data = {
            ATTR_DOMAIN: domain.lower(),
            ATTR_SERVICE: service.lower(),
            ATTR_SERVICE_DATA: service_data,
            ATTR_SERVICE_CALL_ID: call_id,
        }

        if blocking:
            fut = asyncio.Future(loop=self._hass.loop)

            @callback
            def service_executed(event):
                """Handle an executed service."""
                if event.data[ATTR_SERVICE_CALL_ID] == call_id:
                    fut.set_result(True)

            unsub = self._hass.bus.async_listen(
                EVENT_SERVICE_EXECUTED, service_executed)

        self._hass.bus.async_fire(EVENT_CALL_SERVICE, event_data)

        if blocking:
            done, _ = yield from asyncio.wait(
                [fut], loop=self._hass.loop, timeout=SERVICE_CALL_LIMIT)
            success = bool(done)
            unsub()
            return success

    @asyncio.coroutine
    def _event_to_service_call(self, event):
        """Handle the SERVICE_CALLED events from the EventBus."""
        service_data = event.data.get(ATTR_SERVICE_DATA) or {}
        domain = event.data.get(ATTR_DOMAIN).lower()
        service = event.data.get(ATTR_SERVICE).lower()
        call_id = event.data.get(ATTR_SERVICE_CALL_ID)

        if not self.has_service(domain, service):
            if event.origin == EventOrigin.local:
                _LOGGER.warning("Unable to find service %s/%s",
                                domain, service)
            return

        service_handler = self._services[domain][service]

        def fire_service_executed():
            """Fire service executed event."""
            if not call_id:
                return

            data = {ATTR_SERVICE_CALL_ID: call_id}

            if (service_handler.is_coroutinefunction or
                    service_handler.is_callback):
                self._hass.bus.async_fire(EVENT_SERVICE_EXECUTED, data)
            else:
                self._hass.bus.fire(EVENT_SERVICE_EXECUTED, data)

        try:
            if service_handler.schema:
                service_data = service_handler.schema(service_data)
        except vol.Invalid as ex:
            _LOGGER.error("Invalid service data for %s.%s: %s",
                          domain, service, humanize_error(service_data, ex))
            fire_service_executed()
            return

        service_call = ServiceCall(domain, service, service_data, call_id)

        try:
            if service_handler.is_callback:
                service_handler.func(service_call)
                fire_service_executed()
            elif service_handler.is_coroutinefunction:
                yield from service_handler.func(service_call)
                fire_service_executed()
            else:
                def execute_service():
                    """Execute a service and fires a SERVICE_EXECUTED event."""
                    service_handler.func(service_call)
                    fire_service_executed()

                yield from self._hass.async_add_job(execute_service)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error executing service %s', service_call)


class Config(object):
    """Configuration settings for Home Assistant."""

    def __init__(self):
        """Initialize a new config object."""
        self.latitude = None  # type: Optional[float]
        self.longitude = None  # type: Optional[float]
        self.elevation = None  # type: Optional[int]
        self.location_name = None  # type: Optional[str]
        self.time_zone = None  # type: Optional[str]
        self.units = METRIC_SYSTEM  # type: UnitSystem

        # If True, pip install is skipped for requirements on startup
        self.skip_pip = False  # type: bool

        # List of loaded components
        self.components = set()

        # Remote.API object pointing at local API
        self.api = None

        # Directory that holds the configuration
        self.config_dir = None

        # List of allowed external dirs to access
        self.whitelist_external_dirs = set()

    def distance(self: object, lat: float, lon: float) -> float:
        """Calculate distance from Home Assistant.

        Async friendly.
        """
        return self.units.length(
            location.distance(self.latitude, self.longitude, lat, lon), 'm')

    def path(self, *path):
        """Generate path to the file within the configuration directory.

        Async friendly.
        """
        if self.config_dir is None:
            raise HomeAssistantError("config_dir is not set")
        return os.path.join(self.config_dir, *path)

    def is_allowed_path(self, path: str) -> bool:
        """Check if the path is valid for access from outside."""
        assert path is not None

        parent = pathlib.Path(path).parent
        try:
            parent = parent.resolve()  # pylint: disable=no-member
        except (FileNotFoundError, RuntimeError, PermissionError):
            return False

        for whitelisted_path in self.whitelist_external_dirs:
            try:
                parent.relative_to(whitelisted_path)
                return True
            except ValueError:
                pass

        return False

    def as_dict(self):
        """Create a dictionary representation of this dict.

        Async friendly.
        """
        time_zone = self.time_zone or dt_util.UTC

        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'elevation': self.elevation,
            'unit_system': self.units.as_dict(),
            'location_name': self.location_name,
            'time_zone': time_zone.zone,
            'components': self.components,
            'config_dir': self.config_dir,
            'whitelist_external_dirs': self.whitelist_external_dirs,
            'version': __version__
        }


def _async_create_timer(hass):
    """Create a timer that will start on HOMEASSISTANT_START."""
    handle = None

    @callback
    def fire_time_event(nxt):
        """Fire next time event."""
        nonlocal handle

        hass.bus.async_fire(EVENT_TIME_CHANGED,
                            {ATTR_NOW: dt_util.utcnow()})
        nxt += 1
        slp_seconds = nxt - monotonic()

        if slp_seconds < 0:
            _LOGGER.error('Timer got out of sync. Resetting')
            nxt = monotonic() + 1
            slp_seconds = 1

        handle = hass.loop.call_later(slp_seconds, fire_time_event, nxt)

    @callback
    def stop_timer(event):
        """Stop the timer."""
        if handle is not None:
            handle.cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_timer)

    _LOGGER.info("Timer:starting")
    fire_time_event(monotonic())
