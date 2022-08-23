"""
Core components of Home Assistant.

Home Assistant is a Home Automation framework for observing the state
of entities and react to changes.
"""
from __future__ import annotations

import asyncio
from collections.abc import (
    Awaitable,
    Callable,
    Collection,
    Coroutine,
    Iterable,
    Mapping,
)
from contextvars import ContextVar
import datetime
import enum
import functools
import logging
import os
import pathlib
import re
import threading
from time import monotonic
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
    cast,
    overload,
)
from urllib.parse import urlparse

from typing_extensions import ParamSpec
import voluptuous as vol
import yarl

from . import block_async_io, loader, util
from .backports.enum import StrEnum
from .const import (
    ATTR_DOMAIN,
    ATTR_FRIENDLY_NAME,
    ATTR_SERVICE,
    ATTR_SERVICE_DATA,
    CONF_UNIT_SYSTEM_IMPERIAL,
    EVENT_CALL_SERVICE,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_STATE_CHANGED,
    LENGTH_METERS,
    MATCH_ALL,
    MAX_LENGTH_EVENT_EVENT_TYPE,
    MAX_LENGTH_STATE_STATE,
    __version__,
)
from .exceptions import (
    HomeAssistantError,
    InvalidEntityFormatError,
    InvalidStateError,
    MaxLengthExceeded,
    ServiceNotFound,
    Unauthorized,
)
from .util import dt as dt_util, location, ulid as ulid_util
from .util.async_ import (
    fire_coroutine_threadsafe,
    run_callback_threadsafe,
    shutdown_run_callback_threadsafe,
)
from .util.read_only_dict import ReadOnlyDict
from .util.timeout import TimeoutManager
from .util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM, UnitSystem

# Typing imports that create a circular dependency
if TYPE_CHECKING:
    from .auth import AuthManager
    from .components.http import ApiConfig, HomeAssistantHTTP
    from .config_entries import ConfigEntries


STAGE_1_SHUTDOWN_TIMEOUT = 100
STAGE_2_SHUTDOWN_TIMEOUT = 60
STAGE_3_SHUTDOWN_TIMEOUT = 30

block_async_io.enable()

_T = TypeVar("_T")
_R = TypeVar("_R")
_R_co = TypeVar("_R_co", covariant=True)
_P = ParamSpec("_P")
# Internal; not helpers.typing.UNDEFINED due to circular dependency
_UNDEF: dict[Any, Any] = {}
_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])
CALLBACK_TYPE = Callable[[], None]  # pylint: disable=invalid-name

CORE_STORAGE_KEY = "core.config"
CORE_STORAGE_VERSION = 1

DOMAIN = "homeassistant"

# How long to wait to log tasks that are blocking
BLOCK_LOG_TIMEOUT = 60

# How long we wait for the result of a service call
SERVICE_CALL_LIMIT = 10  # seconds


class ConfigSource(StrEnum):
    """Source of core configuration."""

    DEFAULT = "default"
    DISCOVERED = "discovered"
    STORAGE = "storage"
    YAML = "yaml"


# SOURCE_* are deprecated as of Home Assistant 2022.2, use ConfigSource instead
SOURCE_DISCOVERED = ConfigSource.DISCOVERED.value
SOURCE_STORAGE = ConfigSource.STORAGE.value
SOURCE_YAML = ConfigSource.YAML.value

# How long to wait until things that run on startup have to finish.
TIMEOUT_EVENT_START = 15

MAX_EXPECTED_ENTITY_IDS = 16384

_LOGGER = logging.getLogger(__name__)

_cv_hass: ContextVar[HomeAssistant] = ContextVar("current_entry")


@functools.lru_cache(MAX_EXPECTED_ENTITY_IDS)
def split_entity_id(entity_id: str) -> tuple[str, str]:
    """Split a state entity ID into domain and object ID."""
    domain, _, object_id = entity_id.partition(".")
    if not domain or not object_id:
        raise ValueError(f"Invalid entity ID {entity_id}")
    return domain, object_id


VALID_ENTITY_ID = re.compile(r"^(?!.+__)(?!_)[\da-z_]+(?<!_)\.(?!_)[\da-z_]+(?<!_)$")


def valid_entity_id(entity_id: str) -> bool:
    """Test if an entity ID is a valid format.

    Format: <domain>.<entity> where both are slugs.
    """
    return VALID_ENTITY_ID.match(entity_id) is not None


def valid_state(state: str) -> bool:
    """Test if a state is valid."""
    return len(state) <= MAX_LENGTH_STATE_STATE


def callback(func: _CallableT) -> _CallableT:
    """Annotation to mark method as safe to call from within the event loop."""
    setattr(func, "_hass_callback", True)
    return func


def is_callback(func: Callable[..., Any]) -> bool:
    """Check if function is safe to be called in the event loop."""
    return getattr(func, "_hass_callback", False) is True


@callback
def async_get_hass() -> HomeAssistant:
    """Return the HomeAssistant instance.

    Raises LookupError if no HomeAssistant instance is available.

    This should be used where it's very cumbersome or downright impossible to pass
    hass to the code which needs it.
    """
    return _cv_hass.get()


@enum.unique
class HassJobType(enum.Enum):
    """Represent a job type."""

    Coroutinefunction = 1
    Callback = 2
    Executor = 3


class HassJob(Generic[_P, _R_co]):
    """Represent a job to be run later.

    We check the callable type in advance
    so we can avoid checking it every time
    we run the job.
    """

    __slots__ = ("job_type", "target")

    def __init__(self, target: Callable[_P, _R_co]) -> None:
        """Create a job object."""
        self.target = target
        self.job_type = _get_hassjob_callable_job_type(target)

    def __repr__(self) -> str:
        """Return the job."""
        return f"<Job {self.job_type} {self.target}>"


def _get_hassjob_callable_job_type(target: Callable[..., Any]) -> HassJobType:
    """Determine the job type from the callable."""
    # Check for partials to properly determine if coroutine function
    check_target = target
    while isinstance(check_target, functools.partial):
        check_target = check_target.func

    if asyncio.iscoroutinefunction(check_target):
        return HassJobType.Coroutinefunction
    if is_callback(check_target):
        return HassJobType.Callback
    if asyncio.iscoroutine(check_target):
        raise ValueError("Coroutine not allowed to be passed to HassJob")
    return HassJobType.Executor


class CoreState(enum.Enum):
    """Represent the current state of Home Assistant."""

    not_running = "NOT_RUNNING"
    starting = "STARTING"
    running = "RUNNING"
    stopping = "STOPPING"
    final_write = "FINAL_WRITE"
    stopped = "STOPPED"

    def __str__(self) -> str:
        """Return the event."""
        return self.value


class HomeAssistant:
    """Root object of the Home Assistant home automation."""

    auth: AuthManager
    http: HomeAssistantHTTP = None  # type: ignore[assignment]
    config_entries: ConfigEntries = None  # type: ignore[assignment]

    def __new__(cls) -> HomeAssistant:
        """Set the _cv_hass context variable."""
        hass = super().__new__(cls)
        _cv_hass.set(hass)
        return hass

    def __init__(self) -> None:
        """Initialize new Home Assistant object."""
        self.loop = asyncio.get_running_loop()
        self._pending_tasks: list[asyncio.Future[Any]] = []
        self._track_task = True
        self.bus = EventBus(self)
        self.services = ServiceRegistry(self)
        self.states = StateMachine(self.bus, self.loop)
        self.config = Config(self)
        self.components = loader.Components(self)
        self.helpers = loader.Helpers(self)
        # This is a dictionary that any component can store any data on.
        self.data: dict[str, Any] = {}
        self.state: CoreState = CoreState.not_running
        self.exit_code: int = 0
        # If not None, use to signal end-of-loop
        self._stopped: asyncio.Event | None = None
        # Timeout handler for Core/Helper namespace
        self.timeout: TimeoutManager = TimeoutManager()

    @property
    def is_running(self) -> bool:
        """Return if Home Assistant is running."""
        return self.state in (CoreState.starting, CoreState.running)

    @property
    def is_stopping(self) -> bool:
        """Return if Home Assistant is stopping."""
        return self.state in (CoreState.stopping, CoreState.final_write)

    def start(self) -> int:
        """Start Home Assistant.

        Note: This function is only used for testing.
        For regular use, use "await hass.run()".
        """
        # Register the async start
        fire_coroutine_threadsafe(self.async_start(), self.loop)

        # Run forever
        # Block until stopped
        _LOGGER.info("Starting Home Assistant core loop")
        self.loop.run_forever()
        return self.exit_code

    async def async_run(self, *, attach_signals: bool = True) -> int:
        """Home Assistant main entry point.

        Start Home Assistant and block until stopped.

        This method is a coroutine.
        """
        if self.state != CoreState.not_running:
            raise RuntimeError("Home Assistant is already running")

        # _async_stop will set this instead of stopping the loop
        self._stopped = asyncio.Event()

        await self.async_start()
        if attach_signals:
            # pylint: disable=import-outside-toplevel
            from .helpers.signal import async_register_signal_handling

            async_register_signal_handling(self)

        await self._stopped.wait()
        return self.exit_code

    async def async_start(self) -> None:
        """Finalize startup from inside the event loop.

        This method is a coroutine.
        """
        _LOGGER.info("Starting Home Assistant")
        setattr(self.loop, "_thread_ident", threading.get_ident())

        self.state = CoreState.starting
        self.bus.async_fire(EVENT_CORE_CONFIG_UPDATE)
        self.bus.async_fire(EVENT_HOMEASSISTANT_START)

        try:
            # Only block for EVENT_HOMEASSISTANT_START listener
            self.async_stop_track_tasks()
            async with self.timeout.async_timeout(TIMEOUT_EVENT_START):
                await self.async_block_till_done()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Something is blocking Home Assistant from wrapping up the "
                "start up phase. We're going to continue anyway. Please "
                "report the following info at https://github.com/home-assistant/core/issues: %s",
                ", ".join(self.config.components),
            )

        # Allow automations to set up the start triggers before changing state
        await asyncio.sleep(0)

        if self.state != CoreState.starting:
            _LOGGER.warning(
                "Home Assistant startup has been interrupted. "
                "Its state may be inconsistent"
            )
            return

        self.state = CoreState.running
        self.bus.async_fire(EVENT_CORE_CONFIG_UPDATE)
        self.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

    def add_job(
        self, target: Callable[..., Any] | Coroutine[Any, Any, Any], *args: Any
    ) -> None:
        """Add a job to be executed by the event loop or by an executor.

        If the job is either a coroutine or decorated with @callback, it will be
        run by the event loop, if not it will be run by an executor.

        target: target to call.
        args: parameters for method to call.
        """
        if target is None:
            raise ValueError("Don't call add_job with None")
        self.loop.call_soon_threadsafe(self.async_add_job, target, *args)

    @overload
    @callback
    def async_add_job(
        self, target: Callable[..., Coroutine[Any, Any, _R]], *args: Any
    ) -> asyncio.Future[_R] | None:
        ...

    @overload
    @callback
    def async_add_job(
        self, target: Callable[..., Coroutine[Any, Any, _R] | _R], *args: Any
    ) -> asyncio.Future[_R] | None:
        ...

    @overload
    @callback
    def async_add_job(
        self, target: Coroutine[Any, Any, _R], *args: Any
    ) -> asyncio.Future[_R] | None:
        ...

    @callback
    def async_add_job(
        self,
        target: Callable[..., Coroutine[Any, Any, _R] | _R] | Coroutine[Any, Any, _R],
        *args: Any,
    ) -> asyncio.Future[_R] | None:
        """Add a job to be executed by the event loop or by an executor.

        If the job is either a coroutine or decorated with @callback, it will be
        run by the event loop, if not it will be run by an executor.

        This method must be run in the event loop.

        target: target to call.
        args: parameters for method to call.
        """
        if target is None:
            raise ValueError("Don't call async_add_job with None")

        if asyncio.iscoroutine(target):
            return self.async_create_task(target)

        # This code path is performance sensitive and uses
        # if TYPE_CHECKING to avoid the overhead of constructing
        # the type used for the cast. For history see:
        # https://github.com/home-assistant/core/pull/71960
        if TYPE_CHECKING:
            target = cast(Callable[..., Union[Coroutine[Any, Any, _R], _R]], target)
        return self.async_add_hass_job(HassJob(target), *args)

    @overload
    @callback
    def async_add_hass_job(
        self, hassjob: HassJob[..., Coroutine[Any, Any, _R]], *args: Any
    ) -> asyncio.Future[_R] | None:
        ...

    @overload
    @callback
    def async_add_hass_job(
        self, hassjob: HassJob[..., Coroutine[Any, Any, _R] | _R], *args: Any
    ) -> asyncio.Future[_R] | None:
        ...

    @callback
    def async_add_hass_job(
        self, hassjob: HassJob[..., Coroutine[Any, Any, _R] | _R], *args: Any
    ) -> asyncio.Future[_R] | None:
        """Add a HassJob from within the event loop.

        This method must be run in the event loop.
        hassjob: HassJob to call.
        args: parameters for method to call.
        """
        task: asyncio.Future[_R]
        # This code path is performance sensitive and uses
        # if TYPE_CHECKING to avoid the overhead of constructing
        # the type used for the cast. For history see:
        # https://github.com/home-assistant/core/pull/71960
        if hassjob.job_type == HassJobType.Coroutinefunction:
            if TYPE_CHECKING:
                hassjob.target = cast(
                    Callable[..., Coroutine[Any, Any, _R]], hassjob.target
                )
            task = self.loop.create_task(hassjob.target(*args))
        elif hassjob.job_type == HassJobType.Callback:
            if TYPE_CHECKING:
                hassjob.target = cast(Callable[..., _R], hassjob.target)
            self.loop.call_soon(hassjob.target, *args)
            return None
        else:
            if TYPE_CHECKING:
                hassjob.target = cast(Callable[..., _R], hassjob.target)
            task = self.loop.run_in_executor(None, hassjob.target, *args)

        # If a task is scheduled
        if self._track_task:
            self._pending_tasks.append(task)

        return task

    def create_task(self, target: Coroutine[Any, Any, Any]) -> None:
        """Add task to the executor pool.

        target: target to call.
        """
        self.loop.call_soon_threadsafe(self.async_create_task, target)

    @callback
    def async_create_task(self, target: Coroutine[Any, Any, _R]) -> asyncio.Task[_R]:
        """Create a task from within the eventloop.

        This method must be run in the event loop.

        target: target to call.
        """
        task = self.loop.create_task(target)

        if self._track_task:
            self._pending_tasks.append(task)

        return task

    @callback
    def async_add_executor_job(
        self, target: Callable[..., _T], *args: Any
    ) -> asyncio.Future[_T]:
        """Add an executor job from within the event loop."""
        task = self.loop.run_in_executor(None, target, *args)

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

    @overload
    @callback
    def async_run_hass_job(
        self, hassjob: HassJob[..., Coroutine[Any, Any, _R]], *args: Any
    ) -> asyncio.Future[_R] | None:
        ...

    @overload
    @callback
    def async_run_hass_job(
        self, hassjob: HassJob[..., Coroutine[Any, Any, _R] | _R], *args: Any
    ) -> asyncio.Future[_R] | None:
        ...

    @callback
    def async_run_hass_job(
        self, hassjob: HassJob[..., Coroutine[Any, Any, _R] | _R], *args: Any
    ) -> asyncio.Future[_R] | None:
        """Run a HassJob from within the event loop.

        This method must be run in the event loop.

        hassjob: HassJob
        args: parameters for method to call.
        """
        # This code path is performance sensitive and uses
        # if TYPE_CHECKING to avoid the overhead of constructing
        # the type used for the cast. For history see:
        # https://github.com/home-assistant/core/pull/71960
        if hassjob.job_type == HassJobType.Callback:
            if TYPE_CHECKING:
                hassjob.target = cast(Callable[..., _R], hassjob.target)
            hassjob.target(*args)
            return None

        return self.async_add_hass_job(hassjob, *args)

    @overload
    @callback
    def async_run_job(
        self, target: Callable[..., Coroutine[Any, Any, _R]], *args: Any
    ) -> asyncio.Future[_R] | None:
        ...

    @overload
    @callback
    def async_run_job(
        self, target: Callable[..., Coroutine[Any, Any, _R] | _R], *args: Any
    ) -> asyncio.Future[_R] | None:
        ...

    @overload
    @callback
    def async_run_job(
        self, target: Coroutine[Any, Any, _R], *args: Any
    ) -> asyncio.Future[_R] | None:
        ...

    @callback
    def async_run_job(
        self,
        target: Callable[..., Coroutine[Any, Any, _R] | _R] | Coroutine[Any, Any, _R],
        *args: Any,
    ) -> asyncio.Future[_R] | None:
        """Run a job from within the event loop.

        This method must be run in the event loop.

        target: target to call.
        args: parameters for method to call.
        """
        if asyncio.iscoroutine(target):
            return self.async_create_task(target)

        # This code path is performance sensitive and uses
        # if TYPE_CHECKING to avoid the overhead of constructing
        # the type used for the cast. For history see:
        # https://github.com/home-assistant/core/pull/71960
        if TYPE_CHECKING:
            target = cast(Callable[..., Union[Coroutine[Any, Any, _R], _R]], target)
        return self.async_run_hass_job(HassJob(target), *args)

    def block_till_done(self) -> None:
        """Block until all pending work is done."""
        asyncio.run_coroutine_threadsafe(
            self.async_block_till_done(), self.loop
        ).result()

    async def async_block_till_done(self) -> None:
        """Block until all pending work is done."""
        # To flush out any call_soon_threadsafe
        await asyncio.sleep(0)
        start_time: float | None = None

        while self._pending_tasks:
            pending = [task for task in self._pending_tasks if not task.done()]
            self._pending_tasks.clear()
            if pending:
                await self._await_and_log_pending(pending)

                if start_time is None:
                    # Avoid calling monotonic() until we know
                    # we may need to start logging blocked tasks.
                    start_time = 0
                elif start_time == 0:
                    # If we have waited twice then we set the start
                    # time
                    start_time = monotonic()
                elif monotonic() - start_time > BLOCK_LOG_TIMEOUT:
                    # We have waited at least three loops and new tasks
                    # continue to block. At this point we start
                    # logging all waiting tasks.
                    for task in pending:
                        _LOGGER.debug("Waiting for task: %s", task)
            else:
                await asyncio.sleep(0)

    async def _await_and_log_pending(self, pending: Iterable[Awaitable[Any]]) -> None:
        """Await and log tasks that take a long time."""
        wait_time = 0
        while pending:
            _, pending = await asyncio.wait(pending, timeout=BLOCK_LOG_TIMEOUT)
            if not pending:
                return
            wait_time += BLOCK_LOG_TIMEOUT
            for task in pending:
                _LOGGER.debug("Waited %s seconds for task: %s", wait_time, task)

    def stop(self) -> None:
        """Stop Home Assistant and shuts down all threads."""
        if self.state == CoreState.not_running:  # just ignore
            return
        fire_coroutine_threadsafe(self.async_stop(), self.loop)

    async def async_stop(self, exit_code: int = 0, *, force: bool = False) -> None:
        """Stop Home Assistant and shuts down all threads.

        The "force" flag commands async_stop to proceed regardless of
        Home Assistant's current state. You should not set this flag
        unless you're testing.

        This method is a coroutine.
        """
        if not force:
            # Some tests require async_stop to run,
            # regardless of the state of the loop.
            if self.state == CoreState.not_running:  # just ignore
                return
            if self.state in [CoreState.stopping, CoreState.final_write]:
                _LOGGER.info("Additional call to async_stop was ignored")
                return
            if self.state == CoreState.starting:
                # This may not work
                _LOGGER.warning(
                    "Stopping Home Assistant before startup has completed may fail"
                )

        # stage 1
        self.state = CoreState.stopping
        self.async_track_tasks()
        self.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        try:
            async with self.timeout.async_timeout(STAGE_1_SHUTDOWN_TIMEOUT):
                await self.async_block_till_done()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for shutdown stage 1 to complete, the shutdown will continue"
            )

        # stage 2
        self.state = CoreState.final_write
        self.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
        try:
            async with self.timeout.async_timeout(STAGE_2_SHUTDOWN_TIMEOUT):
                await self.async_block_till_done()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for shutdown stage 2 to complete, the shutdown will continue"
            )

        # stage 3
        self.state = CoreState.not_running
        self.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)

        # Prevent run_callback_threadsafe from scheduling any additional
        # callbacks in the event loop as callbacks created on the futures
        # it returns will never run after the final `self.async_block_till_done`
        # which will cause the futures to block forever when waiting for
        # the `result()` which will cause a deadlock when shutting down the executor.
        shutdown_run_callback_threadsafe(self.loop)

        try:
            async with self.timeout.async_timeout(STAGE_3_SHUTDOWN_TIMEOUT):
                await self.async_block_till_done()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for shutdown stage 3 to complete, the shutdown will continue"
            )

        self.exit_code = exit_code
        self.state = CoreState.stopped

        if self._stopped is not None:
            self._stopped.set()


class Context:
    """The context that triggered something."""

    __slots__ = ("user_id", "parent_id", "id", "origin_event")

    def __init__(
        self,
        user_id: str | None = None,
        parent_id: str | None = None,
        id: str | None = None,  # pylint: disable=redefined-builtin
    ) -> None:
        """Init the context."""
        self.id = id or ulid_util.ulid()
        self.user_id = user_id
        self.parent_id = parent_id
        self.origin_event: Event | None = None

    def __eq__(self, other: Any) -> bool:
        """Compare contexts."""
        return bool(self.__class__ == other.__class__ and self.id == other.id)

    def as_dict(self) -> dict[str, str | None]:
        """Return a dictionary representation of the context."""
        return {"id": self.id, "parent_id": self.parent_id, "user_id": self.user_id}


class EventOrigin(enum.Enum):
    """Represent the origin of an event."""

    local = "LOCAL"
    remote = "REMOTE"

    def __str__(self) -> str:
        """Return the event."""
        return self.value


class Event:
    """Representation of an event within the bus."""

    __slots__ = ["event_type", "data", "origin", "time_fired", "context"]

    def __init__(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        origin: EventOrigin = EventOrigin.local,
        time_fired: datetime.datetime | None = None,
        context: Context | None = None,
    ) -> None:
        """Initialize a new event."""
        self.event_type = event_type
        self.data = data or {}
        self.origin = origin
        self.time_fired = time_fired or dt_util.utcnow()
        self.context: Context = context or Context(
            id=ulid_util.ulid(dt_util.utc_to_timestamp(self.time_fired))
        )

    def __hash__(self) -> int:
        """Make hashable."""
        # The only event type that shares context are the TIME_CHANGED
        return hash((self.event_type, self.context.id, self.time_fired))

    def as_dict(self) -> dict[str, Any]:
        """Create a dict representation of this Event.

        Async friendly.
        """
        return {
            "event_type": self.event_type,
            "data": dict(self.data),
            "origin": str(self.origin.value),
            "time_fired": self.time_fired.isoformat(),
            "context": self.context.as_dict(),
        }

    def __repr__(self) -> str:
        """Return the representation."""
        if self.data:
            return f"<Event {self.event_type}[{str(self.origin)[0]}]: {util.repr_helper(self.data)}>"

        return f"<Event {self.event_type}[{str(self.origin)[0]}]>"

    def __eq__(self, other: Any) -> bool:
        """Return the comparison."""
        return (  # type: ignore[no-any-return]
            self.__class__ == other.__class__
            and self.event_type == other.event_type
            and self.data == other.data
            and self.origin == other.origin
            and self.time_fired == other.time_fired
            and self.context == other.context
        )


class _FilterableJob(NamedTuple):
    """Event listener job to be executed with optional filter."""

    job: HassJob[[Event], Coroutine[Any, Any, None] | None]
    event_filter: Callable[[Event], bool] | None
    run_immediately: bool


class EventBus:
    """Allow the firing of and listening for events."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a new event bus."""
        self._listeners: dict[str, list[_FilterableJob]] = {}
        self._hass = hass

    @callback
    def async_listeners(self) -> dict[str, int]:
        """Return dictionary with events and the number of listeners.

        This method must be run in the event loop.
        """
        return {key: len(listeners) for key, listeners in self._listeners.items()}

    @property
    def listeners(self) -> dict[str, int]:
        """Return dictionary with events and the number of listeners."""
        return run_callback_threadsafe(self._hass.loop, self.async_listeners).result()

    def fire(
        self,
        event_type: str,
        event_data: dict[str, Any] | None = None,
        origin: EventOrigin = EventOrigin.local,
        context: Context | None = None,
    ) -> None:
        """Fire an event."""
        self._hass.loop.call_soon_threadsafe(
            self.async_fire, event_type, event_data, origin, context
        )

    @callback
    def async_fire(
        self,
        event_type: str,
        event_data: dict[str, Any] | None = None,
        origin: EventOrigin = EventOrigin.local,
        context: Context | None = None,
        time_fired: datetime.datetime | None = None,
    ) -> None:
        """Fire an event.

        This method must be run in the event loop.
        """
        if len(event_type) > MAX_LENGTH_EVENT_EVENT_TYPE:
            raise MaxLengthExceeded(
                event_type, "event_type", MAX_LENGTH_EVENT_EVENT_TYPE
            )

        listeners = self._listeners.get(event_type, [])

        # EVENT_HOMEASSISTANT_CLOSE should go only to this listeners
        match_all_listeners = self._listeners.get(MATCH_ALL)
        if match_all_listeners is not None and event_type != EVENT_HOMEASSISTANT_CLOSE:
            listeners = match_all_listeners + listeners

        event = Event(event_type, event_data, origin, time_fired, context)
        if not event.context.origin_event:
            event.context.origin_event = event

        _LOGGER.debug("Bus:Handling %s", event)

        if not listeners:
            return

        for job, event_filter, run_immediately in listeners:
            if event_filter is not None:
                try:
                    if not event_filter(event):
                        continue
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Error in event filter")
                    continue
            if run_immediately:
                try:
                    job.target(event)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Error running job: %s", job)
            else:
                self._hass.async_add_hass_job(job, event)

    def listen(
        self,
        event_type: str,
        listener: Callable[[Event], Coroutine[Any, Any, None] | None],
    ) -> CALLBACK_TYPE:
        """Listen for all events or events of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.
        """
        async_remove_listener = run_callback_threadsafe(
            self._hass.loop, self.async_listen, event_type, listener
        ).result()

        def remove_listener() -> None:
            """Remove the listener."""
            run_callback_threadsafe(self._hass.loop, async_remove_listener).result()

        return remove_listener

    @callback
    def async_listen(
        self,
        event_type: str,
        listener: Callable[[Event], Coroutine[Any, Any, None] | None],
        event_filter: Callable[[Event], bool] | None = None,
        run_immediately: bool = False,
    ) -> CALLBACK_TYPE:
        """Listen for all events or events of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        An optional event_filter, which must be a callable decorated with
        @callback that returns a boolean value, determines if the
        listener callable should run.

        If run_immediately is passed, the callback will be run
        right away instead of using call_soon. Only use this if
        the callback results in scheduling another task.

        This method must be run in the event loop.
        """
        if event_filter is not None and not is_callback(event_filter):
            raise HomeAssistantError(f"Event filter {event_filter} is not a callback")
        if run_immediately and not is_callback(listener):
            raise HomeAssistantError(f"Event listener {listener} is not a callback")
        return self._async_listen_filterable_job(
            event_type, _FilterableJob(HassJob(listener), event_filter, run_immediately)
        )

    @callback
    def _async_listen_filterable_job(
        self, event_type: str, filterable_job: _FilterableJob
    ) -> CALLBACK_TYPE:
        self._listeners.setdefault(event_type, []).append(filterable_job)

        def remove_listener() -> None:
            """Remove the listener."""
            self._async_remove_listener(event_type, filterable_job)

        return remove_listener

    def listen_once(
        self,
        event_type: str,
        listener: Callable[[Event], Coroutine[Any, Any, None] | None],
    ) -> CALLBACK_TYPE:
        """Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Returns function to unsubscribe the listener.
        """
        async_remove_listener = run_callback_threadsafe(
            self._hass.loop, self.async_listen_once, event_type, listener
        ).result()

        def remove_listener() -> None:
            """Remove the listener."""
            run_callback_threadsafe(self._hass.loop, async_remove_listener).result()

        return remove_listener

    @callback
    def async_listen_once(
        self,
        event_type: str,
        listener: Callable[[Event], Coroutine[Any, Any, None] | None],
    ) -> CALLBACK_TYPE:
        """Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Returns registered listener that can be used with remove_listener.

        This method must be run in the event loop.
        """
        filterable_job: _FilterableJob | None = None

        @callback
        def _onetime_listener(event: Event) -> None:
            """Remove listener from event bus and then fire listener."""
            nonlocal filterable_job
            if hasattr(_onetime_listener, "run"):
                return
            # Set variable so that we will never run twice.
            # Because the event bus loop might have async_fire queued multiple
            # times, its possible this listener may already be lined up
            # multiple times as well.
            # This will make sure the second time it does nothing.
            setattr(_onetime_listener, "run", True)
            assert filterable_job is not None
            self._async_remove_listener(event_type, filterable_job)
            self._hass.async_run_job(listener, event)

        functools.update_wrapper(
            _onetime_listener, listener, ("__name__", "__qualname__", "__module__"), []
        )

        filterable_job = _FilterableJob(HassJob(_onetime_listener), None, False)

        return self._async_listen_filterable_job(event_type, filterable_job)

    @callback
    def _async_remove_listener(
        self, event_type: str, filterable_job: _FilterableJob
    ) -> None:
        """Remove a listener of a specific event_type.

        This method must be run in the event loop.
        """
        try:
            self._listeners[event_type].remove(filterable_job)

            # delete event_type list if empty
            if not self._listeners[event_type]:
                self._listeners.pop(event_type)
        except (KeyError, ValueError):
            # KeyError is key event_type listener did not exist
            # ValueError if listener did not exist within event_type
            _LOGGER.exception(
                "Unable to remove unknown job listener %s", filterable_job
            )


_StateT = TypeVar("_StateT", bound="State")


class State:
    """Object to represent a state within the state machine.

    entity_id: the entity that is represented.
    state: the state of the entity
    attributes: extra information on entity and state
    last_changed: last time the state was changed, not the attributes.
    last_updated: last time this object was updated.
    context: Context in which it was created
    domain: Domain of this state.
    object_id: Object id of this state.
    """

    __slots__ = [
        "entity_id",
        "state",
        "attributes",
        "last_changed",
        "last_updated",
        "context",
        "domain",
        "object_id",
        "_as_dict",
    ]

    def __init__(
        self,
        entity_id: str,
        state: str,
        attributes: Mapping[str, Any] | None = None,
        last_changed: datetime.datetime | None = None,
        last_updated: datetime.datetime | None = None,
        context: Context | None = None,
        validate_entity_id: bool | None = True,
    ) -> None:
        """Initialize a new state."""
        state = str(state)

        if validate_entity_id and not valid_entity_id(entity_id):
            raise InvalidEntityFormatError(
                f"Invalid entity id encountered: {entity_id}. "
                "Format should be <domain>.<object_id>"
            )

        if not valid_state(state):
            raise InvalidStateError(
                f"Invalid state encountered for entity ID: {entity_id}. "
                "State max length is 255 characters."
            )

        self.entity_id = entity_id.lower()
        self.state = state
        self.attributes = ReadOnlyDict(attributes or {})
        self.last_updated = last_updated or dt_util.utcnow()
        self.last_changed = last_changed or self.last_updated
        self.context = context or Context()
        self.domain, self.object_id = split_entity_id(self.entity_id)
        self._as_dict: ReadOnlyDict[str, Collection[Any]] | None = None

    def __hash__(self) -> int:
        """Make the state hashable.

        State objects are effectively immutable.
        """
        return hash((id(self), self.last_updated))

    @property
    def name(self) -> str:
        """Name of this state."""
        return self.attributes.get(ATTR_FRIENDLY_NAME) or self.object_id.replace(
            "_", " "
        )

    def as_dict(self) -> ReadOnlyDict[str, Collection[Any]]:
        """Return a dict representation of the State.

        Async friendly.

        To be used for JSON serialization.
        Ensures: state == State.from_dict(state.as_dict())
        """
        if not self._as_dict:
            last_changed_isoformat = self.last_changed.isoformat()
            if self.last_changed == self.last_updated:
                last_updated_isoformat = last_changed_isoformat
            else:
                last_updated_isoformat = self.last_updated.isoformat()
            self._as_dict = ReadOnlyDict(
                {
                    "entity_id": self.entity_id,
                    "state": self.state,
                    "attributes": self.attributes,
                    "last_changed": last_changed_isoformat,
                    "last_updated": last_updated_isoformat,
                    "context": ReadOnlyDict(self.context.as_dict()),
                }
            )
        return self._as_dict

    @classmethod
    def from_dict(cls: type[_StateT], json_dict: dict[str, Any]) -> _StateT | None:
        """Initialize a state from a dict.

        Async friendly.

        Ensures: state == State.from_json_dict(state.to_json_dict())
        """
        if not (json_dict and "entity_id" in json_dict and "state" in json_dict):
            return None

        last_changed = json_dict.get("last_changed")

        if isinstance(last_changed, str):
            last_changed = dt_util.parse_datetime(last_changed)

        last_updated = json_dict.get("last_updated")

        if isinstance(last_updated, str):
            last_updated = dt_util.parse_datetime(last_updated)

        if context := json_dict.get("context"):
            context = Context(id=context.get("id"), user_id=context.get("user_id"))

        return cls(
            json_dict["entity_id"],
            json_dict["state"],
            json_dict.get("attributes"),
            last_changed,
            last_updated,
            context,
        )

    def expire(self) -> None:
        """Mark the state as old.

        We give up the original reference to the context to ensure
        the context can be garbage collected by replacing it with
        a new one with the same id to ensure the old state
        can still be examined for comparison against the new state.

        Since we are always going to fire a EVENT_STATE_CHANGED event
        after we remove a state from the state machine we need to make
        sure we don't end up holding a reference to the original context
        since it can never be garbage collected as each event would
        reference the previous one.
        """
        self.context = Context(
            self.context.user_id, self.context.parent_id, self.context.id
        )

    def __eq__(self, other: Any) -> bool:
        """Return the comparison of the state."""
        return (  # type: ignore[no-any-return]
            self.__class__ == other.__class__
            and self.entity_id == other.entity_id
            and self.state == other.state
            and self.attributes == other.attributes
            and self.context == other.context
        )

    def __repr__(self) -> str:
        """Return the representation of the states."""
        attrs = f"; {util.repr_helper(self.attributes)}" if self.attributes else ""

        return (
            f"<state {self.entity_id}={self.state}{attrs}"
            f" @ {dt_util.as_local(self.last_changed).isoformat()}>"
        )


class StateMachine:
    """Helper class that tracks the state of different entities."""

    def __init__(self, bus: EventBus, loop: asyncio.events.AbstractEventLoop) -> None:
        """Initialize state machine."""
        self._states: dict[str, State] = {}
        self._reservations: set[str] = set()
        self._bus = bus
        self._loop = loop

    def entity_ids(self, domain_filter: str | None = None) -> list[str]:
        """List of entity ids that are being tracked."""
        future = run_callback_threadsafe(
            self._loop, self.async_entity_ids, domain_filter
        )
        return future.result()

    @callback
    def async_entity_ids(
        self, domain_filter: str | Iterable[str] | None = None
    ) -> list[str]:
        """List of entity ids that are being tracked.

        This method must be run in the event loop.
        """
        if domain_filter is None:
            return list(self._states)

        if isinstance(domain_filter, str):
            domain_filter = (domain_filter.lower(),)

        return [
            state.entity_id
            for state in self._states.values()
            if state.domain in domain_filter
        ]

    @callback
    def async_entity_ids_count(
        self, domain_filter: str | Iterable[str] | None = None
    ) -> int:
        """Count the entity ids that are being tracked.

        This method must be run in the event loop.
        """
        if domain_filter is None:
            return len(self._states)

        if isinstance(domain_filter, str):
            domain_filter = (domain_filter.lower(),)

        return len(
            [None for state in self._states.values() if state.domain in domain_filter]
        )

    def all(self, domain_filter: str | Iterable[str] | None = None) -> list[State]:
        """Create a list of all states."""
        return run_callback_threadsafe(
            self._loop, self.async_all, domain_filter
        ).result()

    @callback
    def async_all(
        self, domain_filter: str | Iterable[str] | None = None
    ) -> list[State]:
        """Create a list of all states matching the filter.

        This method must be run in the event loop.
        """
        if domain_filter is None:
            return list(self._states.values())

        if isinstance(domain_filter, str):
            domain_filter = (domain_filter.lower(),)

        return [
            state for state in self._states.values() if state.domain in domain_filter
        ]

    def get(self, entity_id: str) -> State | None:
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
        return run_callback_threadsafe(
            self._loop, self.async_remove, entity_id
        ).result()

    @callback
    def async_remove(self, entity_id: str, context: Context | None = None) -> bool:
        """Remove the state of an entity.

        Returns boolean to indicate if an entity was removed.

        This method must be run in the event loop.
        """
        entity_id = entity_id.lower()
        old_state = self._states.pop(entity_id, None)

        if entity_id in self._reservations:
            self._reservations.remove(entity_id)

        if old_state is None:
            return False

        old_state.expire()
        self._bus.async_fire(
            EVENT_STATE_CHANGED,
            {"entity_id": entity_id, "old_state": old_state, "new_state": None},
            EventOrigin.local,
            context=context,
        )
        return True

    def set(
        self,
        entity_id: str,
        new_state: str,
        attributes: Mapping[str, Any] | None = None,
        force_update: bool = False,
        context: Context | None = None,
    ) -> None:
        """Set the state of an entity, add entity if it does not exist.

        Attributes is an optional dict to specify attributes of this state.

        If you just update the attributes and not the state, last changed will
        not be affected.
        """
        run_callback_threadsafe(
            self._loop,
            self.async_set,
            entity_id,
            new_state,
            attributes,
            force_update,
            context,
        ).result()

    @callback
    def async_reserve(self, entity_id: str) -> None:
        """Reserve a state in the state machine for an entity being added.

        This must not fire an event when the state is reserved.

        This avoids a race condition where multiple entities with the same
        entity_id are added.
        """
        entity_id = entity_id.lower()
        if entity_id in self._states or entity_id in self._reservations:
            raise HomeAssistantError(
                "async_reserve must not be called once the state is in the state machine."
            )

        self._reservations.add(entity_id)

    @callback
    def async_available(self, entity_id: str) -> bool:
        """Check to see if an entity_id is available to be used."""
        entity_id = entity_id.lower()
        return entity_id not in self._states and entity_id not in self._reservations

    @callback
    def async_set(
        self,
        entity_id: str,
        new_state: str,
        attributes: Mapping[str, Any] | None = None,
        force_update: bool = False,
        context: Context | None = None,
    ) -> None:
        """Set the state of an entity, add entity if it does not exist.

        Attributes is an optional dict to specify attributes of this state.

        If you just update the attributes and not the state, last changed will
        not be affected.

        This method must be run in the event loop.
        """
        entity_id = entity_id.lower()
        new_state = str(new_state)
        attributes = attributes or {}
        if (old_state := self._states.get(entity_id)) is None:
            same_state = False
            same_attr = False
            last_changed = None
        else:
            same_state = old_state.state == new_state and not force_update
            same_attr = old_state.attributes == attributes
            last_changed = old_state.last_changed if same_state else None

        if same_state and same_attr:
            return

        now = dt_util.utcnow()

        if context is None:
            context = Context(id=ulid_util.ulid(dt_util.utc_to_timestamp(now)))
        state = State(
            entity_id,
            new_state,
            attributes,
            last_changed,
            now,
            context,
            old_state is None,
        )
        if old_state is not None:
            old_state.expire()
        self._states[entity_id] = state
        self._bus.async_fire(
            EVENT_STATE_CHANGED,
            {"entity_id": entity_id, "old_state": old_state, "new_state": state},
            EventOrigin.local,
            context,
            time_fired=now,
        )


class Service:
    """Representation of a callable service."""

    __slots__ = ["job", "schema"]

    def __init__(
        self,
        func: Callable[[ServiceCall], Coroutine[Any, Any, None] | None],
        schema: vol.Schema | None,
        context: Context | None = None,
    ) -> None:
        """Initialize a service."""
        self.job = HassJob(func)
        self.schema = schema


class ServiceCall:
    """Representation of a call to a service."""

    __slots__ = ["domain", "service", "data", "context"]

    def __init__(
        self,
        domain: str,
        service: str,
        data: dict[str, Any] | None = None,
        context: Context | None = None,
    ) -> None:
        """Initialize a service call."""
        self.domain = domain.lower()
        self.service = service.lower()
        self.data = ReadOnlyDict(data or {})
        self.context = context or Context()

    def __repr__(self) -> str:
        """Return the representation of the service."""
        if self.data:
            return (
                f"<ServiceCall {self.domain}.{self.service} "
                f"(c:{self.context.id}): {util.repr_helper(self.data)}>"
            )

        return f"<ServiceCall {self.domain}.{self.service} (c:{self.context.id})>"


class ServiceRegistry:
    """Offer the services over the eventbus."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a service registry."""
        self._services: dict[str, dict[str, Service]] = {}
        self._hass = hass

    @property
    def services(self) -> dict[str, dict[str, Service]]:
        """Return dictionary with per domain a list of available services."""
        return run_callback_threadsafe(self._hass.loop, self.async_services).result()

    @callback
    def async_services(self) -> dict[str, dict[str, Service]]:
        """Return dictionary with per domain a list of available services.

        This method must be run in the event loop.
        """
        return {domain: service.copy() for domain, service in self._services.items()}

    def has_service(self, domain: str, service: str) -> bool:
        """Test if specified service exists.

        Async friendly.
        """
        return service.lower() in self._services.get(domain.lower(), [])

    def register(
        self,
        domain: str,
        service: str,
        service_func: Callable[[ServiceCall], Coroutine[Any, Any, None] | None],
        schema: vol.Schema | None = None,
    ) -> None:
        """
        Register a service.

        Schema is called to coerce and validate the service data.
        """
        run_callback_threadsafe(
            self._hass.loop, self.async_register, domain, service, service_func, schema
        ).result()

    @callback
    def async_register(
        self,
        domain: str,
        service: str,
        service_func: Callable[[ServiceCall], Coroutine[Any, Any, None] | None],
        schema: vol.Schema | None = None,
    ) -> None:
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
            EVENT_SERVICE_REGISTERED, {ATTR_DOMAIN: domain, ATTR_SERVICE: service}
        )

    def remove(self, domain: str, service: str) -> None:
        """Remove a registered service from service handler."""
        run_callback_threadsafe(
            self._hass.loop, self.async_remove, domain, service
        ).result()

    @callback
    def async_remove(self, domain: str, service: str) -> None:
        """Remove a registered service from service handler.

        This method must be run in the event loop.
        """
        domain = domain.lower()
        service = service.lower()

        if service not in self._services.get(domain, {}):
            _LOGGER.warning("Unable to remove unknown service %s/%s", domain, service)
            return

        self._services[domain].pop(service)

        if not self._services[domain]:
            self._services.pop(domain)

        self._hass.bus.async_fire(
            EVENT_SERVICE_REMOVED, {ATTR_DOMAIN: domain, ATTR_SERVICE: service}
        )

    def call(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        blocking: bool = False,
        context: Context | None = None,
        limit: float | None = SERVICE_CALL_LIMIT,
        target: dict[str, Any] | None = None,
    ) -> bool | None:
        """
        Call a service.

        See description of async_call for details.
        """
        return asyncio.run_coroutine_threadsafe(
            self.async_call(
                domain, service, service_data, blocking, context, limit, target
            ),
            self._hass.loop,
        ).result()

    async def async_call(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        blocking: bool = False,
        context: Context | None = None,
        limit: float | None = SERVICE_CALL_LIMIT,
        target: dict[str, Any] | None = None,
    ) -> bool | None:
        """
        Call a service.

        Specify blocking=True to wait until service is executed.
        Waits a maximum of limit, which may be None for no timeout.

        If blocking = True, will return boolean if service executed
        successfully within limit.

        This method will fire an event to indicate the service has been called.

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

        if target:
            service_data.update(target)

        if handler.schema:
            try:
                processed_data: dict[str, Any] = handler.schema(service_data)
            except vol.Invalid:
                _LOGGER.debug(
                    "Invalid data for service call %s.%s: %s",
                    domain,
                    service,
                    service_data,
                )
                raise
        else:
            processed_data = service_data

        service_call = ServiceCall(domain, service, processed_data, context)

        self._hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                ATTR_DOMAIN: domain.lower(),
                ATTR_SERVICE: service.lower(),
                ATTR_SERVICE_DATA: service_data,
            },
            context=context,
        )

        coro = self._execute_service(handler, service_call)
        if not blocking:
            self._run_service_in_background(coro, service_call)
            return None

        task = self._hass.async_create_task(coro)
        try:
            await asyncio.wait({task}, timeout=limit)
        except asyncio.CancelledError:
            # Task calling us was cancelled, so cancel service call task, and wait for
            # it to be cancelled, within reason, before leaving.
            _LOGGER.debug("Service call was cancelled: %s", service_call)
            task.cancel()
            await asyncio.wait({task}, timeout=SERVICE_CALL_LIMIT)
            raise

        if task.cancelled():
            # Service call task was cancelled some other way, such as during shutdown.
            _LOGGER.debug("Service was cancelled: %s", service_call)
            raise asyncio.CancelledError
        if task.done():
            # Propagate any exceptions that might have happened during service call.
            task.result()
            # Service call completed successfully!
            return True
        # Service call task did not complete before timeout expired.
        # Let it keep running in background.
        self._run_service_in_background(task, service_call)
        _LOGGER.debug("Service did not complete before timeout: %s", service_call)
        return False

    def _run_service_in_background(
        self,
        coro_or_task: Coroutine[Any, Any, None] | asyncio.Task[None],
        service_call: ServiceCall,
    ) -> None:
        """Run service call in background, catching and logging any exceptions."""

        async def catch_exceptions() -> None:
            try:
                await coro_or_task
            except Unauthorized:
                _LOGGER.warning(
                    "Unauthorized service called %s/%s",
                    service_call.domain,
                    service_call.service,
                )
            except asyncio.CancelledError:
                _LOGGER.debug("Service was cancelled: %s", service_call)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error executing service: %s", service_call)

        self._hass.async_create_task(catch_exceptions())

    async def _execute_service(
        self, handler: Service, service_call: ServiceCall
    ) -> None:
        """Execute a service."""
        if handler.job.job_type == HassJobType.Coroutinefunction:
            await cast(Callable[[ServiceCall], Awaitable[None]], handler.job.target)(
                service_call
            )
        elif handler.job.job_type == HassJobType.Callback:
            cast(Callable[[ServiceCall], None], handler.job.target)(service_call)
        else:
            await self._hass.async_add_executor_job(
                cast(Callable[[ServiceCall], None], handler.job.target), service_call
            )


class Config:
    """Configuration settings for Home Assistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a new config object."""
        self.hass = hass

        self.latitude: float = 0
        self.longitude: float = 0
        self.elevation: int = 0
        self.location_name: str = "Home"
        self.time_zone: str = "UTC"
        self.units: UnitSystem = METRIC_SYSTEM
        self.internal_url: str | None = None
        self.external_url: str | None = None
        self.currency: str = "EUR"

        self.config_source: ConfigSource = ConfigSource.DEFAULT

        # If True, pip install is skipped for requirements on startup
        self.skip_pip: bool = False

        # List of loaded components
        self.components: set[str] = set()

        # API (HTTP) server configuration
        self.api: ApiConfig | None = None

        # Directory that holds the configuration
        self.config_dir: str | None = None

        # List of allowed external dirs to access
        self.allowlist_external_dirs: set[str] = set()

        # List of allowed external URLs that integrations may use
        self.allowlist_external_urls: set[str] = set()

        # Dictionary of Media folders that integrations may use
        self.media_dirs: dict[str, str] = {}

        # If Home Assistant is running in safe mode
        self.safe_mode: bool = False

        # Use legacy template behavior
        self.legacy_templates: bool = False

    def distance(self, lat: float, lon: float) -> float | None:
        """Calculate distance from Home Assistant.

        Async friendly.
        """
        return self.units.length(
            location.distance(self.latitude, self.longitude, lat, lon), LENGTH_METERS
        )

    def path(self, *path: str) -> str:
        """Generate path to the file within the configuration directory.

        Async friendly.
        """
        if self.config_dir is None:
            raise HomeAssistantError("config_dir is not set")
        return os.path.join(self.config_dir, *path)

    def is_allowed_external_url(self, url: str) -> bool:
        """Check if an external URL is allowed."""
        parsed_url = f"{str(yarl.URL(url))}/"

        return any(
            allowed
            for allowed in self.allowlist_external_urls
            if parsed_url.startswith(allowed)
        )

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

        for allowed_path in self.allowlist_external_dirs:
            try:
                thepath.relative_to(allowed_path)
                return True
            except ValueError:
                pass

        return False

    def as_dict(self) -> dict[str, Any]:
        """Create a dictionary representation of the configuration.

        Async friendly.
        """
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
            "unit_system": self.units.as_dict(),
            "location_name": self.location_name,
            "time_zone": self.time_zone,
            "components": self.components,
            "config_dir": self.config_dir,
            # legacy, backwards compat
            "whitelist_external_dirs": self.allowlist_external_dirs,
            "allowlist_external_dirs": self.allowlist_external_dirs,
            "allowlist_external_urls": self.allowlist_external_urls,
            "version": __version__,
            "config_source": self.config_source,
            "safe_mode": self.safe_mode,
            "state": self.hass.state.value,
            "external_url": self.external_url,
            "internal_url": self.internal_url,
            "currency": self.currency,
        }

    def set_time_zone(self, time_zone_str: str) -> None:
        """Help to set the time zone."""
        if time_zone := dt_util.get_time_zone(time_zone_str):
            self.time_zone = time_zone_str
            dt_util.set_default_time_zone(time_zone)
        else:
            raise ValueError(f"Received invalid time zone {time_zone_str}")

    @callback
    def _update(
        self,
        *,
        source: ConfigSource,
        latitude: float | None = None,
        longitude: float | None = None,
        elevation: int | None = None,
        unit_system: str | None = None,
        location_name: str | None = None,
        time_zone: str | None = None,
        # pylint: disable=dangerous-default-value # _UNDEFs not modified
        external_url: str | dict[Any, Any] | None = _UNDEF,
        internal_url: str | dict[Any, Any] | None = _UNDEF,
        currency: str | None = None,
    ) -> None:
        """Update the configuration from a dictionary."""
        self.config_source = source
        if latitude is not None:
            self.latitude = latitude
        if longitude is not None:
            self.longitude = longitude
        if elevation is not None:
            self.elevation = elevation
        if unit_system is not None:
            if unit_system == CONF_UNIT_SYSTEM_IMPERIAL:
                self.units = IMPERIAL_SYSTEM
            else:
                self.units = METRIC_SYSTEM
        if location_name is not None:
            self.location_name = location_name
        if time_zone is not None:
            self.set_time_zone(time_zone)
        if external_url is not _UNDEF:
            self.external_url = cast(Optional[str], external_url)
        if internal_url is not _UNDEF:
            self.internal_url = cast(Optional[str], internal_url)
        if currency is not None:
            self.currency = currency

    async def async_update(self, **kwargs: Any) -> None:
        """Update the configuration from a dictionary."""
        self._update(source=ConfigSource.STORAGE, **kwargs)
        await self.async_store()
        self.hass.bus.async_fire(EVENT_CORE_CONFIG_UPDATE, kwargs)

    async def async_load(self) -> None:
        """Load [homeassistant] core config."""
        # Circular dep
        # pylint: disable=import-outside-toplevel
        from .helpers.storage import Store

        store = Store[dict[str, Any]](
            self.hass,
            CORE_STORAGE_VERSION,
            CORE_STORAGE_KEY,
            private=True,
            atomic_writes=True,
        )

        if not (data := await store.async_load()):
            return

        # In 2021.9 we fixed validation to disallow a path (because that's never correct)
        # but this data still lives in storage, so we print a warning.
        if data.get("external_url") and urlparse(data["external_url"]).path not in (
            "",
            "/",
        ):
            _LOGGER.warning("Invalid external_url set. It's not allowed to have a path")

        if data.get("internal_url") and urlparse(data["internal_url"]).path not in (
            "",
            "/",
        ):
            _LOGGER.warning("Invalid internal_url set. It's not allowed to have a path")

        self._update(
            source=ConfigSource.STORAGE,
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            elevation=data.get("elevation"),
            unit_system=data.get("unit_system"),
            location_name=data.get("location_name"),
            time_zone=data.get("time_zone"),
            external_url=data.get("external_url", _UNDEF),
            internal_url=data.get("internal_url", _UNDEF),
            currency=data.get("currency"),
        )

    async def async_store(self) -> None:
        """Store [homeassistant] core config."""
        # Circular dep
        # pylint: disable=import-outside-toplevel
        from .helpers.storage import Store

        data = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
            "unit_system": self.units.name,
            "location_name": self.location_name,
            "time_zone": self.time_zone,
            "external_url": self.external_url,
            "internal_url": self.internal_url,
            "currency": self.currency,
        }

        store: Store[dict[str, Any]] = Store(
            self.hass,
            CORE_STORAGE_VERSION,
            CORE_STORAGE_KEY,
            private=True,
            atomic_writes=True,
        )
        await store.async_save(data)
