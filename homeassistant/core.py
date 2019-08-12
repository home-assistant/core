"""
Core components of Home Assistant.

Home Assistant is a Home Automation framework for observing the state
of entities and react to changes.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import datetime
import enum
import functools
import logging
import os
import pathlib
import sys
import threading
from time import monotonic
import uuid

from types import MappingProxyType
from typing import (  # noqa: F401 pylint: disable=unused-import
    Optional, Any, Callable, List, TypeVar, Dict, Coroutine, Set,
    TYPE_CHECKING, Awaitable, Iterator)

from async_timeout import timeout
import attr
import voluptuous as vol

from homeassistant.const import (
    ATTR_DOMAIN, ATTR_FRIENDLY_NAME, ATTR_NOW, ATTR_SERVICE,
    ATTR_SERVICE_DATA, ATTR_SECONDS, EVENT_CALL_SERVICE,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    EVENT_HOMEASSISTANT_CLOSE, EVENT_SERVICE_REMOVED,
    EVENT_SERVICE_REGISTERED, EVENT_STATE_CHANGED,
    EVENT_TIME_CHANGED, EVENT_TIMER_OUT_OF_SYNC, MATCH_ALL, __version__)
from homeassistant import loader
from homeassistant.exceptions import (
    HomeAssistantError, InvalidEntityFormatError, InvalidStateError,
    Unauthorized, ServiceNotFound)
from homeassistant.util.async_ import (
    run_coroutine_threadsafe, run_callback_threadsafe,
    fire_coroutine_threadsafe)
from homeassistant import util
import homeassistant.util.dt as dt_util
from homeassistant.util import location, slugify
from homeassistant.util.unit_system import UnitSystem, METRIC_SYSTEM  # NOQA

# Typing imports that create a circular dependency
# pylint: disable=using-constant-test
if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntries  # noqa

# pylint: disable=invalid-name
T = TypeVar('T')
CALLABLE_T = TypeVar('CALLABLE_T', bound=Callable)
CALLBACK_TYPE = Callable[[], None]
# pylint: enable=invalid-name

DOMAIN = 'homeassistant'

# How long we wait for the result of a service call
SERVICE_CALL_LIMIT = 10  # seconds

# How long to wait till things that run on startup have to finish.
TIMEOUT_EVENT_START = 15

_LOGGER = logging.getLogger(__name__)


def split_entity_id(entity_id: str) -> List[str]:
    """Split a state entity_id into domain, object_id."""
    return entity_id.split(".", 1)


def valid_entity_id(entity_id: str) -> bool:
    """Test if an entity ID is a valid format.

    Format: <domain>.<entity> where both are slugs.
    """
    return ('.' in entity_id and
            slugify(entity_id) == entity_id.replace('.', '_', 1))


def valid_state(state: str) -> bool:
    """Test if a state is valid."""
    return len(state) < 256


def callback(func: CALLABLE_T) -> CALLABLE_T:
    """Annotation to mark method as safe to call from within the event loop."""
    setattr(func, '_hass_callback', True)
    return func


def is_callback(func: Callable[..., Any]) -> bool:
    """Check if function is safe to be called in the event loop."""
    return getattr(func, '_hass_callback', False) is True


@callback
def async_loop_exception_handler(_: Any, context: Dict) -> None:
    """Handle all exception inside the core loop."""
    kwargs = {}
    exception = context.get('exception')
    if exception:
        kwargs['exc_info'] = (type(exception), exception,
                              exception.__traceback__)

    _LOGGER.error(  # type: ignore
        "Error doing job: %s", context['message'], **kwargs)


class CoreState(enum.Enum):
    """Represent the current state of Home Assistant."""

    not_running = 'NOT_RUNNING'
    starting = 'STARTING'
    running = 'RUNNING'
    stopping = 'STOPPING'

    def __str__(self) -> str:
        """Return the event."""
        return self.value  # type: ignore


class HomeAssistant:
    """Root object of the Home Assistant home automation."""

    def __init__(
            self,
            loop: Optional[asyncio.events.AbstractEventLoop] = None) -> None:
        """Initialize new Home Assistant object."""
        self.loop = loop or asyncio.get_event_loop()

        executor_opts = {'max_workers': None}  # type: Dict[str, Any]
        if sys.version_info[:2] >= (3, 6):
            executor_opts['thread_name_prefix'] = 'SyncWorker'

        self.executor = ThreadPoolExecutor(**executor_opts)
        self.loop.set_default_executor(self.executor)
        self.loop.set_exception_handler(async_loop_exception_handler)
        self._pending_tasks = []  # type: list
        self._track_task = True
        self.bus = EventBus(self)
        self.services = ServiceRegistry(self)
        self.states = StateMachine(self.bus, self.loop)
        self.config = Config()  # type: Config
        self.components = loader.Components(self)
        self.helpers = loader.Helpers(self)
        # This is a dictionary that any component can store any data on.
        self.data = {}  # type: dict
        self.state = CoreState.not_running
        self.exit_code = 0  # type: int
        self.config_entries = None  # type: Optional[ConfigEntries]
        # If not None, use to signal end-of-loop
        self._stopped = None  # type: Optional[asyncio.Event]

    @property
    def is_running(self) -> bool:
        """Return if Home Assistant is running."""
        return self.state in (CoreState.starting, CoreState.running)

    def start(self) -> int:
        """Start home assistant.

        Note: This function is only used for testing.
        For regular use, use "await hass.run()".
        """
        # Register the async start
        fire_coroutine_threadsafe(self.async_start(), self.loop)

        # Run forever
        try:
            # Block until stopped
            _LOGGER.info("Starting Home Assistant core loop")
            self.loop.run_forever()
        finally:
            self.loop.close()
        return self.exit_code

    async def async_run(self, *, attach_signals: bool = True) -> int:
        """Home Assistant main entry point.

        Start Home Assistant and block until stopped.

        This method is a coroutine.
        """
        if self.state != CoreState.not_running:
            raise RuntimeError("HASS is already running")

        # _async_stop will set this instead of stopping the loop
        self._stopped = asyncio.Event()

        await self.async_start()
        if attach_signals:
            from homeassistant.helpers.signal \
                    import async_register_signal_handling
            async_register_signal_handling(self)

        await self._stopped.wait()
        return self.exit_code

    async def async_start(self) -> None:
        """Finalize startup from inside the event loop.

        This method is a coroutine.
        """
        _LOGGER.info("Starting Home Assistant")
        self.state = CoreState.starting

        setattr(self.loop, '_thread_ident', threading.get_ident())
        self.bus.async_fire(EVENT_HOMEASSISTANT_START)

        try:
            # Only block for EVENT_HOMEASSISTANT_START listener
            self.async_stop_track_tasks()
            with timeout(TIMEOUT_EVENT_START):
                await self.async_block_till_done()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                'Something is blocking Home Assistant from wrapping up the '
                'start up phase. We\'re going to continue anyway. Please '
                'report the following info at http://bit.ly/2ogP58T : %s',
                ', '.join(self.config.components))

        # Allow automations to set up the start triggers before changing state
        await asyncio.sleep(0)

        if self.state != CoreState.starting:
            _LOGGER.warning(
                'Home Assistant startup has been interrupted. '
                'Its state may be inconsistent.')
            return

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
    def async_add_job(
            self,
            target: Callable[..., Any],
            *args: Any) -> Optional[asyncio.Future]:
        """Add a job from within the event loop.

        This method must be run in the event loop.

        target: target to call.
        args: parameters for method to call.
        """
        task = None

        # Check for partials to properly determine if coroutine function
        check_target = target
        while isinstance(check_target, functools.partial):
            check_target = check_target.func

        if asyncio.iscoroutine(check_target):
            task = self.loop.create_task(target)  # type: ignore
        elif is_callback(check_target):
            self.loop.call_soon(target, *args)
        elif asyncio.iscoroutinefunction(check_target):
            task = self.loop.create_task(target(*args))
        else:
            task = self.loop.run_in_executor(  # type: ignore
                None, target, *args)

        # If a task is scheduled
        if self._track_task and task is not None:
            self._pending_tasks.append(task)

        return task

    @callback
    def async_create_task(self, target: Coroutine) -> asyncio.tasks.Task:
        """Create a task from within the eventloop.

        This method must be run in the event loop.

        target: target to call.
        """
        task = self.loop.create_task(target)  # type: asyncio.tasks.Task

        if self._track_task:
            self._pending_tasks.append(task)

        return task

    @callback
    def async_add_executor_job(
            self,
            target: Callable[..., T],
            *args: Any) -> Awaitable[T]:
        """Add an executor job from within the event loop."""
        task = self.loop.run_in_executor(
            None, target, *args)

        # If a task is scheduled
        if self._track_task:
            self._pending_tasks.append(task)

        return task

    @callback
    def async_track_tasks(self) -> None:
        """Track tasks so you can wait for all tasks to be done."""
        self._track_task = True

    @callback
    def async_stop_track_tasks(self) -> None:
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

    async def async_block_till_done(self) -> None:
        """Block till all pending work is done."""
        # To flush out any call_soon_threadsafe
        await asyncio.sleep(0)

        while self._pending_tasks:
            pending = [task for task in self._pending_tasks
                       if not task.done()]
            self._pending_tasks.clear()
            if pending:
                await asyncio.wait(pending)
            else:
                await asyncio.sleep(0)

    def stop(self) -> None:
        """Stop Home Assistant and shuts down all threads."""
        if self.state == CoreState.not_running:  # just ignore
            return
        fire_coroutine_threadsafe(self.async_stop(), self.loop)

    async def async_stop(self, exit_code: int = 0, *,
                         force: bool = False) -> None:
        """Stop Home Assistant and shuts down all threads.

        The "force" flag commands async_stop to proceed regardless of
        Home Assistan't current state. You should not set this flag
        unless you're testing.

        This method is a coroutine.
        """
        if not force:
            # Some tests require async_stop to run,
            # regardless of the state of the loop.
            if self.state == CoreState.not_running:  # just ignore
                return
            if self.state == CoreState.stopping:
                _LOGGER.info("async_stop called twice: ignored")
                return
            if self.state == CoreState.starting:
                # This may not work
                _LOGGER.warning("async_stop called before startup is complete")

        # stage 1
        self.state = CoreState.stopping
        self.async_track_tasks()
        self.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await self.async_block_till_done()

        # stage 2
        self.state = CoreState.not_running
        self.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
        await self.async_block_till_done()
        self.executor.shutdown()

        self.exit_code = exit_code

        if self._stopped is not None:
            self._stopped.set()
        else:
            self.loop.stop()


@attr.s(slots=True, frozen=True)
class Context:
    """The context that triggered something."""

    user_id = attr.ib(
        type=str,
        default=None,
    )
    parent_id = attr.ib(
        type=Optional[str],
        default=None
    )
    id = attr.ib(
        type=str,
        default=attr.Factory(lambda: uuid.uuid4().hex),
    )

    def as_dict(self) -> dict:
        """Return a dictionary representation of the context."""
        return {
            'id': self.id,
            'parent_id': self.parent_id,
            'user_id': self.user_id,
        }


class EventOrigin(enum.Enum):
    """Represent the origin of an event."""

    local = 'LOCAL'
    remote = 'REMOTE'

    def __str__(self) -> str:
        """Return the event."""
        return self.value  # type: ignore


class Event:
    """Representation of an event within the bus."""

    __slots__ = ['event_type', 'data', 'origin', 'time_fired', 'context']

    def __init__(self, event_type: str, data: Optional[Dict] = None,
                 origin: EventOrigin = EventOrigin.local,
                 time_fired: Optional[int] = None,
                 context: Optional[Context] = None) -> None:
        """Initialize a new event."""
        self.event_type = event_type
        self.data = data or {}
        self.origin = origin
        self.time_fired = time_fired or dt_util.utcnow()
        self.context = context or Context()

    def as_dict(self) -> Dict:
        """Create a dict representation of this Event.

        Async friendly.
        """
        return {
            'event_type': self.event_type,
            'data': dict(self.data),
            'origin': str(self.origin),
            'time_fired': self.time_fired,
            'context': self.context.as_dict()
        }

    def __repr__(self) -> str:
        """Return the representation."""
        # pylint: disable=maybe-no-member
        if self.data:
            return "<Event {}[{}]: {}>".format(
                self.event_type, str(self.origin)[0],
                util.repr_helper(self.data))

        return "<Event {}[{}]>".format(self.event_type,
                                       str(self.origin)[0])

    def __eq__(self, other: Any) -> bool:
        """Return the comparison."""
        return (self.__class__ == other.__class__ and  # type: ignore
                self.event_type == other.event_type and
                self.data == other.data and
                self.origin == other.origin and
                self.time_fired == other.time_fired and
                self.context == other.context)


class EventBus:
    """Allow the firing of and listening for events."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a new event bus."""
        self._listeners = {}  # type: Dict[str, List[Callable]]
        self._hass = hass

    @callback
    def async_listeners(self) -> Dict[str, int]:
        """Return dictionary with events and the number of listeners.

        This method must be run in the event loop.
        """
        return {key: len(self._listeners[key])
                for key in self._listeners}

    @property
    def listeners(self) -> Dict[str, int]:
        """Return dictionary with events and the number of listeners."""
        return run_callback_threadsafe(  # type: ignore
            self._hass.loop, self.async_listeners
        ).result()

    def fire(self, event_type: str, event_data: Optional[Dict] = None,
             origin: EventOrigin = EventOrigin.local,
             context: Optional[Context] = None) -> None:
        """Fire an event."""
        self._hass.loop.call_soon_threadsafe(
            self.async_fire, event_type, event_data, origin, context)

    @callback
    def async_fire(self, event_type: str, event_data: Optional[Dict] = None,
                   origin: EventOrigin = EventOrigin.local,
                   context: Optional[Context] = None) -> None:
        """Fire an event.

        This method must be run in the event loop.
        """
        listeners = self._listeners.get(event_type, [])

        # EVENT_HOMEASSISTANT_CLOSE should go only to his listeners
        match_all_listeners = self._listeners.get(MATCH_ALL)
        if (match_all_listeners is not None and
                event_type != EVENT_HOMEASSISTANT_CLOSE):
            listeners = match_all_listeners + listeners

        event = Event(event_type, event_data, origin, None, context)

        if event_type != EVENT_TIME_CHANGED:
            _LOGGER.debug("Bus:Handling %s", event)

        if not listeners:
            return

        for func in listeners:
            self._hass.async_add_job(func, event)

    def listen(
            self, event_type: str, listener: Callable) -> CALLBACK_TYPE:
        """Listen for all events or events of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.
        """
        async_remove_listener = run_callback_threadsafe(
            self._hass.loop, self.async_listen, event_type, listener).result()

        def remove_listener() -> None:
            """Remove the listener."""
            run_callback_threadsafe(
                self._hass.loop, async_remove_listener).result()

        return remove_listener

    @callback
    def async_listen(
            self, event_type: str, listener: Callable) -> CALLBACK_TYPE:
        """Listen for all events or events of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        This method must be run in the event loop.
        """
        if event_type in self._listeners:
            self._listeners[event_type].append(listener)
        else:
            self._listeners[event_type] = [listener]

        def remove_listener() -> None:
            """Remove the listener."""
            self._async_remove_listener(event_type, listener)

        return remove_listener

    def listen_once(
            self, event_type: str, listener: Callable) -> CALLBACK_TYPE:
        """Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Returns function to unsubscribe the listener.
        """
        async_remove_listener = run_callback_threadsafe(
            self._hass.loop, self.async_listen_once, event_type, listener,
        ).result()

        def remove_listener() -> None:
            """Remove the listener."""
            run_callback_threadsafe(
                self._hass.loop, async_remove_listener).result()

        return remove_listener

    @callback
    def async_listen_once(
            self, event_type: str, listener: Callable) -> CALLBACK_TYPE:
        """Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Returns registered listener that can be used with remove_listener.

        This method must be run in the event loop.
        """
        @callback
        def onetime_listener(event: Event) -> None:
            """Remove listener from event bus and then fire listener."""
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
    def _async_remove_listener(
            self, event_type: str, listener: Callable) -> None:
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


class State:
    """Object to represent a state within the state machine.

    entity_id: the entity that is represented.
    state: the state of the entity
    attributes: extra information on entity and state
    last_changed: last time the state was changed, not the attributes.
    last_updated: last time this object was updated.
    context: Context in which it was created
    """

    __slots__ = ['entity_id', 'state', 'attributes',
                 'last_changed', 'last_updated', 'context']

    def __init__(self, entity_id: str, state: Any,
                 attributes: Optional[Dict] = None,
                 last_changed: Optional[datetime.datetime] = None,
                 last_updated: Optional[datetime.datetime] = None,
                 context: Optional[Context] = None,
                 # Temp, because database can still store invalid entity IDs
                 # Remove with 1.0 or in 2020.
                 temp_invalid_id_bypass: Optional[bool] = False) -> None:
        """Initialize a new state."""
        state = str(state)

        if not valid_entity_id(entity_id) and not temp_invalid_id_bypass:
            raise InvalidEntityFormatError((
                "Invalid entity id encountered: {}. "
                "Format should be <domain>.<object_id>").format(entity_id))

        if not valid_state(state):
            raise InvalidStateError((
                "Invalid state encountered for entity id: {}. "
                "State max length is 255 characters.").format(entity_id))

        self.entity_id = entity_id.lower()
        self.state = state  # type: str
        self.attributes = MappingProxyType(attributes or {})
        self.last_updated = last_updated or dt_util.utcnow()
        self.last_changed = last_changed or self.last_updated
        self.context = context or Context()

    @property
    def domain(self) -> str:
        """Domain of this state."""
        return split_entity_id(self.entity_id)[0]

    @property
    def object_id(self) -> str:
        """Object id of this state."""
        return split_entity_id(self.entity_id)[1]

    @property
    def name(self) -> str:
        """Name of this state."""
        return (
            self.attributes.get(ATTR_FRIENDLY_NAME) or
            self.object_id.replace('_', ' '))

    def as_dict(self) -> Dict:
        """Return a dict representation of the State.

        Async friendly.

        To be used for JSON serialization.
        Ensures: state == State.from_dict(state.as_dict())
        """
        return {'entity_id': self.entity_id,
                'state': self.state,
                'attributes': dict(self.attributes),
                'last_changed': self.last_changed,
                'last_updated': self.last_updated,
                'context': self.context.as_dict()}

    @classmethod
    def from_dict(cls, json_dict: Dict) -> Any:
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

        context = json_dict.get('context')
        if context:
            context = Context(
                id=context.get('id'),
                user_id=context.get('user_id'),
            )

        return cls(json_dict['entity_id'], json_dict['state'],
                   json_dict.get('attributes'), last_changed, last_updated,
                   context)

    def __eq__(self, other: Any) -> bool:
        """Return the comparison of the state."""
        return (self.__class__ == other.__class__ and  # type: ignore
                self.entity_id == other.entity_id and
                self.state == other.state and
                self.attributes == other.attributes and
                self.context == other.context)

    def __repr__(self) -> str:
        """Return the representation of the states."""
        attrs = "; {}".format(util.repr_helper(self.attributes)) \
            if self.attributes else ""

        return "<state {}={}{} @ {}>".format(
            self.entity_id, self.state, attrs,
            dt_util.as_local(self.last_changed).isoformat())


class StateMachine:
    """Helper class that tracks the state of different entities."""

    def __init__(self, bus: EventBus,
                 loop: asyncio.events.AbstractEventLoop) -> None:
        """Initialize state machine."""
        self._states = {}  # type: Dict[str, State]
        self._bus = bus
        self._loop = loop

    def entity_ids(self, domain_filter: Optional[str] = None) -> List[str]:
        """List of entity ids that are being tracked."""
        future = run_callback_threadsafe(
            self._loop, self.async_entity_ids, domain_filter
        )
        return future.result()  # type: ignore

    @callback
    def async_entity_ids(
            self, domain_filter: Optional[str] = None) -> List[str]:
        """List of entity ids that are being tracked.

        This method must be run in the event loop.
        """
        if domain_filter is None:
            return list(self._states.keys())

        domain_filter = domain_filter.lower()

        return [state.entity_id for state in self._states.values()
                if state.domain == domain_filter]

    def all(self) -> List[State]:
        """Create a list of all states."""
        return run_callback_threadsafe(  # type: ignore
            self._loop, self.async_all).result()

    @callback
    def async_all(self) -> List[State]:
        """Create a list of all states.

        This method must be run in the event loop.
        """
        return list(self._states.values())

    def get(self, entity_id: str) -> Optional[State]:
        """Retrieve state of entity_id or None if not found.

        Async friendly.
        """
        return self._states.get(entity_id.lower())

    def is_state(self, entity_id: str, state: str) -> bool:
        """Test if entity exists and is in specified state.

        Async friendly.
        """
        state_obj = self.get(entity_id)
        return state_obj is not None and state_obj.state == state

    def remove(self, entity_id: str) -> bool:
        """Remove the state of an entity.

        Returns boolean to indicate if an entity was removed.
        """
        return run_callback_threadsafe(  # type: ignore
            self._loop, self.async_remove, entity_id).result()

    @callback
    def async_remove(self, entity_id: str) -> bool:
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

    def set(self, entity_id: str, new_state: Any,
            attributes: Optional[Dict] = None,
            force_update: bool = False,
            context: Optional[Context] = None) -> None:
        """Set the state of an entity, add entity if it does not exist.

        Attributes is an optional dict to specify attributes of this state.

        If you just update the attributes and not the state, last changed will
        not be affected.
        """
        run_callback_threadsafe(
            self._loop,
            self.async_set, entity_id, new_state, attributes, force_update,
            context,
        ).result()

    @callback
    def async_set(self, entity_id: str, new_state: Any,
                  attributes: Optional[Dict] = None,
                  force_update: bool = False,
                  context: Optional[Context] = None) -> None:
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
        if old_state is None:
            same_state = False
            same_attr = False
            last_changed = None
        else:
            same_state = (old_state.state == new_state and
                          not force_update)
            same_attr = old_state.attributes == MappingProxyType(attributes)
            last_changed = old_state.last_changed if same_state else None

        if same_state and same_attr:
            return

        if context is None:
            context = Context()

        state = State(entity_id, new_state, attributes, last_changed, None,
                      context)
        self._states[entity_id] = state
        self._bus.async_fire(EVENT_STATE_CHANGED, {
            'entity_id': entity_id,
            'old_state': old_state,
            'new_state': state,
        }, EventOrigin.local, context)


class Service:
    """Representation of a callable service."""

    __slots__ = ['func', 'schema', 'is_callback', 'is_coroutinefunction']

    def __init__(self, func: Callable, schema: Optional[vol.Schema],
                 context: Optional[Context] = None) -> None:
        """Initialize a service."""
        self.func = func
        self.schema = schema
        # Properly detect wrapped functions
        while isinstance(func, functools.partial):
            func = func.func
        self.is_callback = is_callback(func)
        self.is_coroutinefunction = asyncio.iscoroutinefunction(func)


class ServiceCall:
    """Representation of a call to a service."""

    __slots__ = ['domain', 'service', 'data', 'context']

    def __init__(self, domain: str, service: str, data: Optional[Dict] = None,
                 context: Optional[Context] = None) -> None:
        """Initialize a service call."""
        self.domain = domain.lower()
        self.service = service.lower()
        self.data = MappingProxyType(data or {})
        self.context = context or Context()

    def __repr__(self) -> str:
        """Return the representation of the service."""
        if self.data:
            return "<ServiceCall {}.{} (c:{}): {}>".format(
                self.domain, self.service, self.context.id,
                util.repr_helper(self.data))

        return "<ServiceCall {}.{} (c:{})>".format(
            self.domain, self.service, self.context.id)


class ServiceRegistry:
    """Offer the services over the eventbus."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a service registry."""
        self._services = {}  # type: Dict[str, Dict[str, Service]]
        self._hass = hass

    @property
    def services(self) -> Dict[str, Dict[str, Service]]:
        """Return dictionary with per domain a list of available services."""
        return run_callback_threadsafe(  # type: ignore
            self._hass.loop, self.async_services,
        ).result()

    @callback
    def async_services(self) -> Dict[str, Dict[str, Service]]:
        """Return dictionary with per domain a list of available services.

        This method must be run in the event loop.
        """
        return {domain: self._services[domain].copy()
                for domain in self._services}

    def has_service(self, domain: str, service: str) -> bool:
        """Test if specified service exists.

        Async friendly.
        """
        return service.lower() in self._services.get(domain.lower(), [])

    def register(self, domain: str, service: str, service_func: Callable,
                 schema: Optional[vol.Schema] = None) -> None:
        """
        Register a service.

        Schema is called to coerce and validate the service data.
        """
        run_callback_threadsafe(
            self._hass.loop,
            self.async_register, domain, service, service_func, schema
        ).result()

    @callback
    def async_register(self, domain: str, service: str, service_func: Callable,
                       schema: Optional[vol.Schema] = None) -> None:
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

        self._hass.bus.async_fire(
            EVENT_SERVICE_REGISTERED,
            {ATTR_DOMAIN: domain, ATTR_SERVICE: service}
        )

    def remove(self, domain: str, service: str) -> None:
        """Remove a registered service from service handler."""
        run_callback_threadsafe(
            self._hass.loop, self.async_remove, domain, service).result()

    @callback
    def async_remove(self, domain: str, service: str) -> None:
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

    def call(self, domain: str, service: str,
             service_data: Optional[Dict] = None,
             blocking: bool = False,
             context: Optional[Context] = None) -> Optional[bool]:
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
        return run_coroutine_threadsafe(  # type: ignore
            self.async_call(domain, service, service_data, blocking, context),
            self._hass.loop
        ).result()

    async def async_call(self, domain: str, service: str,
                         service_data: Optional[Dict] = None,
                         blocking: bool = False,
                         context: Optional[Context] = None) -> Optional[bool]:
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
        domain = domain.lower()
        service = service.lower()
        context = context or Context()
        service_data = service_data or {}

        try:
            handler = self._services[domain][service]
        except KeyError:
            raise ServiceNotFound(domain, service) from None

        if handler.schema:
            processed_data = handler.schema(service_data)
        else:
            processed_data = service_data

        service_call = ServiceCall(domain, service, processed_data, context)

        self._hass.bus.async_fire(EVENT_CALL_SERVICE, {
            ATTR_DOMAIN: domain.lower(),
            ATTR_SERVICE: service.lower(),
            ATTR_SERVICE_DATA: service_data,
        }, context=context)

        if not blocking:
            self._hass.async_create_task(
                self._safe_execute(handler, service_call))
            return None

        try:
            with timeout(SERVICE_CALL_LIMIT):
                await asyncio.shield(
                    self._execute_service(handler, service_call))
            return True
        except asyncio.TimeoutError:
            return False

    async def _safe_execute(self, handler: Service,
                            service_call: ServiceCall) -> None:
        """Execute a service and catch exceptions."""
        try:
            await self._execute_service(handler, service_call)
        except Unauthorized:
            _LOGGER.warning('Unauthorized service called %s/%s',
                            service_call.domain, service_call.service)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error executing service %s', service_call)

    async def _execute_service(self, handler: Service,
                               service_call: ServiceCall) -> None:
        """Execute a service."""
        if handler.is_callback:
            handler.func(service_call)
        elif handler.is_coroutinefunction:
            await handler.func(service_call)
        else:
            await self._hass.async_add_executor_job(handler.func, service_call)


class Config:
    """Configuration settings for Home Assistant."""

    def __init__(self) -> None:
        """Initialize a new config object."""
        self.latitude = None  # type: Optional[float]
        self.longitude = None  # type: Optional[float]
        self.elevation = None  # type: Optional[int]
        self.location_name = None  # type: Optional[str]
        self.time_zone = None  # type: Optional[datetime.tzinfo]
        self.units = METRIC_SYSTEM  # type: UnitSystem

        # If True, pip install is skipped for requirements on startup
        self.skip_pip = False  # type: bool

        # List of loaded components
        self.components = set()  # type: set

        # API (HTTP) server configuration, see components.http.ApiConfig
        self.api = None  # type: Optional[Any]

        # Directory that holds the configuration
        self.config_dir = None  # type: Optional[str]

        # List of allowed external dirs to access
        self.whitelist_external_dirs = set()  # type: Set[str]

    def distance(self, lat: float, lon: float) -> Optional[float]:
        """Calculate distance from Home Assistant.

        Async friendly.
        """
        return self.units.length(
            location.distance(self.latitude, self.longitude, lat, lon), 'm')

    def path(self, *path: str) -> str:
        """Generate path to the file within the configuration directory.

        Async friendly.
        """
        if self.config_dir is None:
            raise HomeAssistantError("config_dir is not set")
        return os.path.join(self.config_dir, *path)

    def is_allowed_path(self, path: str) -> bool:
        """Check if the path is valid for access from outside."""
        assert path is not None

        thepath = pathlib.Path(path)
        try:
            # The file path does not have to exist (it's parent should)
            if thepath.exists():
                thepath = thepath.resolve()
            else:
                thepath = thepath.parent.resolve()
        except (FileNotFoundError, RuntimeError, PermissionError):
            return False

        for whitelisted_path in self.whitelist_external_dirs:
            try:
                thepath.relative_to(whitelisted_path)
                return True
            except ValueError:
                pass

        return False

    def as_dict(self) -> Dict:
        """Create a dictionary representation of this dict.

        Async friendly.
        """
        time_zone = dt_util.UTC.zone
        if self.time_zone and getattr(self.time_zone, 'zone'):
            time_zone = getattr(self.time_zone, 'zone')

        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'elevation': self.elevation,
            'unit_system': self.units.as_dict(),
            'location_name': self.location_name,
            'time_zone': time_zone,
            'components': self.components,
            'config_dir': self.config_dir,
            'whitelist_external_dirs': self.whitelist_external_dirs,
            'version': __version__
        }


def _async_create_timer(hass: HomeAssistant) -> None:
    """Create a timer that will start on HOMEASSISTANT_START."""
    handle = None

    def schedule_tick(now: datetime.datetime) -> None:
        """Schedule a timer tick when the next second rolls around."""
        nonlocal handle

        slp_seconds = 1 - (now.microsecond / 10**6)
        target = monotonic() + slp_seconds
        handle = hass.loop.call_later(slp_seconds, fire_time_event, target)

    @callback
    def fire_time_event(target: float) -> None:
        """Fire next time event."""
        now = dt_util.utcnow()

        hass.bus.async_fire(EVENT_TIME_CHANGED,
                            {ATTR_NOW: now})

        # If we are more than a second late, a tick was missed
        late = monotonic() - target
        if late > 1:
            hass.bus.async_fire(EVENT_TIMER_OUT_OF_SYNC,
                                {ATTR_SECONDS: late})

        schedule_tick(now)

    @callback
    def stop_timer(_: Event) -> None:
        """Stop the timer."""
        if handle is not None:
            handle.cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_timer)

    _LOGGER.info("Timer:starting")
    schedule_tick(dt_util.utcnow())
