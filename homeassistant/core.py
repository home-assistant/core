"""Core components of Home Assistant.

Home Assistant is a Home Automation framework for observing the state
of entities and react to changes.
"""

from __future__ import annotations

import asyncio
from collections import UserDict, defaultdict
from collections.abc import (
    Callable,
    Collection,
    Coroutine,
    Iterable,
    KeysView,
    Mapping,
    ValuesView,
)
import concurrent.futures
from dataclasses import dataclass
import datetime
import enum
import functools
import inspect
import logging
import re
import threading
import time
from time import monotonic
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Generic,
    NotRequired,
    Self,
    TypedDict,
    cast,
    overload,
)

from propcache import cached_property, under_cached_property
from typing_extensions import TypeVar
import voluptuous as vol

from . import util
from .const import (
    ATTR_DOMAIN,
    ATTR_FRIENDLY_NAME,
    ATTR_SERVICE,
    ATTR_SERVICE_DATA,
    COMPRESSED_STATE_ATTRIBUTES,
    COMPRESSED_STATE_CONTEXT,
    COMPRESSED_STATE_LAST_CHANGED,
    COMPRESSED_STATE_LAST_UPDATED,
    COMPRESSED_STATE_STATE,
    EVENT_CALL_SERVICE,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_LOGGING_CHANGED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_STATE_CHANGED,
    EVENT_STATE_REPORTED,
    MATCH_ALL,
    MAX_EXPECTED_ENTITY_IDS,
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
    ServiceValidationError,
    Unauthorized,
)
from .helpers.deprecation import (
    DeferredDeprecatedAlias,
    EnumWithDeprecatedMembers,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from .helpers.json import json_bytes, json_fragment
from .helpers.typing import VolSchemaType
from .util import dt as dt_util
from .util.async_ import (
    cancelling,
    create_eager_task,
    get_scheduled_timer_handles,
    run_callback_threadsafe,
    shutdown_run_callback_threadsafe,
)
from .util.event_type import EventType
from .util.executor import InterruptibleThreadPoolExecutor
from .util.hass_dict import HassDict
from .util.json import JsonObjectType
from .util.read_only_dict import ReadOnlyDict
from .util.timeout import TimeoutManager
from .util.ulid import ulid_at_time, ulid_now

# Typing imports that create a circular dependency
if TYPE_CHECKING:
    from .auth import AuthManager
    from .components.http import HomeAssistantHTTP
    from .config_entries import ConfigEntries
    from .helpers.entity import StateInfo

STOPPING_STAGE_SHUTDOWN_TIMEOUT = 20
STOP_STAGE_SHUTDOWN_TIMEOUT = 100
FINAL_WRITE_STAGE_SHUTDOWN_TIMEOUT = 60
CLOSE_STAGE_SHUTDOWN_TIMEOUT = 30


_SENTINEL = object()
_DataT = TypeVar("_DataT", bound=Mapping[str, Any], default=Mapping[str, Any])
type CALLBACK_TYPE = Callable[[], None]

DOMAIN = "homeassistant"

# How long to wait to log tasks that are blocking
BLOCK_LOG_TIMEOUT = 60

type ServiceResponse = JsonObjectType | None
type EntityServiceResponse = dict[str, ServiceResponse]


class ConfigSource(
    enum.StrEnum,
    metaclass=EnumWithDeprecatedMembers,
    deprecated={
        "DEFAULT": ("core_config.ConfigSource.DEFAULT", "2025.11.0"),
        "DISCOVERED": ("core_config.ConfigSource.DISCOVERED", "2025.11.0"),
        "STORAGE": ("core_config.ConfigSource.STORAGE", "2025.11.0"),
        "YAML": ("core_config.ConfigSource.YAML", "2025.11.0"),
    },
):
    """Source of core configuration."""

    DEFAULT = "default"
    DISCOVERED = "discovered"
    STORAGE = "storage"
    YAML = "yaml"


class EventStateEventData(TypedDict):
    """Base class for EVENT_STATE_CHANGED and EVENT_STATE_REPORTED data."""

    entity_id: str
    new_state: State | None


class EventStateChangedData(EventStateEventData):
    """EVENT_STATE_CHANGED data.

    A state changed event is fired when on state write the state is changed.
    """

    old_state: State | None


class EventStateReportedData(EventStateEventData):
    """EVENT_STATE_REPORTED data.

    A state reported event is fired when on state write the state is unchanged.
    """

    old_last_reported: datetime.datetime


def _deprecated_core_config() -> Any:
    # pylint: disable-next=import-outside-toplevel
    from . import core_config

    return core_config.Config


# The Config class was moved to core_config in Home Assistant 2024.11
_DEPRECATED_Config = DeferredDeprecatedAlias(
    _deprecated_core_config, "homeassistant.core_config.Config", "2025.11"
)


# How long to wait until things that run on startup have to finish.
TIMEOUT_EVENT_START = 15


EVENTS_EXCLUDED_FROM_MATCH_ALL = {
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_STATE_REPORTED,
}

_LOGGER = logging.getLogger(__name__)


@functools.lru_cache(MAX_EXPECTED_ENTITY_IDS)
def split_entity_id(entity_id: str) -> tuple[str, str]:
    """Split a state entity ID into domain and object ID."""
    domain, _, object_id = entity_id.partition(".")
    if not domain or not object_id:
        raise ValueError(f"Invalid entity ID {entity_id}")
    return domain, object_id


_OBJECT_ID = r"(?!_)[\da-z_]+(?<!_)"
_DOMAIN = r"(?!.+__)" + _OBJECT_ID
VALID_DOMAIN = re.compile(r"^" + _DOMAIN + r"$")
VALID_ENTITY_ID = re.compile(r"^" + _DOMAIN + r"\." + _OBJECT_ID + r"$")


@functools.lru_cache(64)
def valid_domain(domain: str) -> bool:
    """Test if a domain a valid format."""
    return VALID_DOMAIN.match(domain) is not None


@functools.lru_cache(512)
def valid_entity_id(entity_id: str) -> bool:
    """Test if an entity ID is a valid format.

    Format: <domain>.<entity> where both are slugs.
    """
    return VALID_ENTITY_ID.match(entity_id) is not None


def validate_state(state: str) -> str:
    """Validate a state, raise if it not valid."""
    if len(state) > MAX_LENGTH_STATE_STATE:
        raise InvalidStateError(
            f"Invalid state with length {len(state)}. "
            "State max length is 255 characters."
        )
    return state


def callback[_CallableT: Callable[..., Any]](func: _CallableT) -> _CallableT:
    """Annotation to mark method as safe to call from within the event loop."""
    setattr(func, "_hass_callback", True)
    return func


def is_callback(func: Callable[..., Any]) -> bool:
    """Check if function is safe to be called in the event loop."""
    return getattr(func, "_hass_callback", False) is True


def is_callback_check_partial(target: Callable[..., Any]) -> bool:
    """Check if function is safe to be called in the event loop.

    This version of is_callback will also check if the target is a partial
    and walk the chain of partials to find the original function.
    """
    check_target = target
    while isinstance(check_target, functools.partial):
        check_target = check_target.func
    return is_callback(check_target)


class _Hass(threading.local):
    """Container which makes a HomeAssistant instance available to the event loop."""

    hass: HomeAssistant | None = None


_hass = _Hass()


@callback
def async_get_hass() -> HomeAssistant:
    """Return the HomeAssistant instance.

    Raises HomeAssistantError when called from the wrong thread.

    This should be used where it's very cumbersome or downright impossible to pass
    hass to the code which needs it.
    """
    if not (hass := async_get_hass_or_none()):
        raise HomeAssistantError("async_get_hass called from the wrong thread")
    return hass


def async_get_hass_or_none() -> HomeAssistant | None:
    """Return the HomeAssistant instance or None.

    Returns None when called from the wrong thread.
    """
    return _hass.hass


class ReleaseChannel(enum.StrEnum):
    BETA = "beta"
    DEV = "dev"
    NIGHTLY = "nightly"
    STABLE = "stable"


@callback
def get_release_channel() -> ReleaseChannel:
    """Find release channel based on version number."""
    version = __version__
    if "dev0" in version:
        return ReleaseChannel.DEV
    if "dev" in version:
        return ReleaseChannel.NIGHTLY
    if "b" in version:
        return ReleaseChannel.BETA
    return ReleaseChannel.STABLE


@enum.unique
class HassJobType(enum.Enum):
    """Represent a job type."""

    Coroutinefunction = 1
    Callback = 2
    Executor = 3


class HassJob[**_P, _R_co]:
    """Represent a job to be run later.

    We check the callable type in advance
    so we can avoid checking it every time
    we run the job.
    """

    __slots__ = ("target", "name", "_cancel_on_shutdown", "_cache")

    def __init__(
        self,
        target: Callable[_P, _R_co],
        name: str | None = None,
        *,
        cancel_on_shutdown: bool | None = None,
        job_type: HassJobType | None = None,
    ) -> None:
        """Create a job object."""
        self.target: Final = target
        self.name = name
        self._cancel_on_shutdown = cancel_on_shutdown
        self._cache: dict[str, Any] = {}
        if job_type:
            # Pre-set the cached_property so we
            # avoid the function call
            self._cache["job_type"] = job_type

    @under_cached_property
    def job_type(self) -> HassJobType:
        """Return the job type."""
        return get_hassjob_callable_job_type(self.target)

    @property
    def cancel_on_shutdown(self) -> bool | None:
        """Return if the job should be cancelled on shutdown."""
        return self._cancel_on_shutdown

    def __repr__(self) -> str:
        """Return the job."""
        return f"<Job {self.name} {self.job_type} {self.target}>"


@dataclass(frozen=True)
class HassJobWithArgs:
    """Container for a HassJob and arguments."""

    job: HassJob[..., Coroutine[Any, Any, Any] | Any]
    args: Iterable[Any]


def get_hassjob_callable_job_type(target: Callable[..., Any]) -> HassJobType:
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

    def __new__(cls, config_dir: str) -> Self:
        """Set the _hass thread local data."""
        hass = super().__new__(cls)
        _hass.hass = hass
        return hass

    def __repr__(self) -> str:
        """Return the representation."""
        return f"<HomeAssistant {self.state}>"

    def __init__(self, config_dir: str) -> None:
        """Initialize new Home Assistant object."""
        # pylint: disable-next=import-outside-toplevel
        from . import loader

        # pylint: disable-next=import-outside-toplevel
        from .core_config import Config

        # This is a dictionary that any component can store any data on.
        self.data = HassDict()
        self.loop = asyncio.get_running_loop()
        self._tasks: set[asyncio.Future[Any]] = set()
        self._background_tasks: set[asyncio.Future[Any]] = set()
        self.bus = EventBus(self)
        self.services = ServiceRegistry(self)
        self.states = StateMachine(self.bus, self.loop)
        self.config = Config(self, config_dir)
        self.config.async_initialize()
        self.components = loader.Components(self)
        self.helpers = loader.Helpers(self)
        self.state: CoreState = CoreState.not_running
        self.exit_code: int = 0
        # If not None, use to signal end-of-loop
        self._stopped: asyncio.Event | None = None
        # Timeout handler for Core/Helper namespace
        self.timeout: TimeoutManager = TimeoutManager()
        self._stop_future: concurrent.futures.Future[None] | None = None
        self._shutdown_jobs: list[HassJobWithArgs] = []
        self.import_executor = InterruptibleThreadPoolExecutor(
            max_workers=1, thread_name_prefix="ImportExecutor"
        )
        self.loop_thread_id = getattr(self.loop, "_thread_id")

    def verify_event_loop_thread(self, what: str) -> None:
        """Report and raise if we are not running in the event loop thread."""
        if self.loop_thread_id != threading.get_ident():
            # frame is a circular import, so we import it here
            from .helpers import frame  # pylint: disable=import-outside-toplevel

            frame.report_non_thread_safe_operation(what)

    @property
    def _active_tasks(self) -> set[asyncio.Future[Any]]:
        """Return all active tasks.

        This property is used in bootstrap to log all active tasks
        so we can identify what is blocking startup.

        This property is marked as private to avoid accidental use
        as it is not guaranteed to be present in future versions.
        """
        return self._tasks

    @cached_property
    def is_running(self) -> bool:
        """Return if Home Assistant is running."""
        return self.state in (CoreState.starting, CoreState.running)

    @cached_property
    def is_stopping(self) -> bool:
        """Return if Home Assistant is stopping."""
        return self.state in (CoreState.stopping, CoreState.final_write)

    def set_state(self, state: CoreState) -> None:
        """Set the current state."""
        self.state = state
        for prop in ("is_running", "is_stopping"):
            self.__dict__.pop(prop, None)

    def start(self) -> int:
        """Start Home Assistant.

        Note: This function is only used for testing.
        For regular use, use "await hass.run()".
        """
        # Register the async start
        _future = asyncio.run_coroutine_threadsafe(self.async_start(), self.loop)
        # Run forever
        # Block until stopped
        _LOGGER.info("Starting Home Assistant core loop")
        self.loop.run_forever()
        # The future is never retrieved but we still hold a reference to it
        # to prevent the task from being garbage collected prematurely.
        del _future
        return self.exit_code

    async def async_run(self, *, attach_signals: bool = True) -> int:
        """Home Assistant main entry point.

        Start Home Assistant and block until stopped.

        This method is a coroutine.
        """
        if self.state is not CoreState.not_running:
            raise RuntimeError("Home Assistant is already running")

        # _async_stop will set this instead of stopping the loop
        self._stopped = asyncio.Event()

        await self.async_start()
        if attach_signals:
            # pylint: disable-next=import-outside-toplevel
            from .helpers.signal import async_register_signal_handling

            async_register_signal_handling(self)

        await self._stopped.wait()
        return self.exit_code

    async def async_start(self) -> None:
        """Finalize startup from inside the event loop.

        This method is a coroutine.
        """
        _LOGGER.info("Starting Home Assistant")

        self.set_state(CoreState.starting)
        self.bus.async_fire_internal(EVENT_CORE_CONFIG_UPDATE)
        self.bus.async_fire_internal(EVENT_HOMEASSISTANT_START)

        if not self._tasks:
            pending: set[asyncio.Future[Any]] | None = None
        else:
            _done, pending = await asyncio.wait(
                self._tasks, timeout=TIMEOUT_EVENT_START
            )

        if pending:
            _LOGGER.warning(
                (
                    "Something is blocking Home Assistant from wrapping up the start up"
                    " phase. We're going to continue anyway. Please report the"
                    " following info at"
                    " https://github.com/home-assistant/core/issues: %s"
                    " The system is waiting for tasks: %s"
                ),
                ", ".join(self.config.components),
                self._tasks,
            )

        # Allow automations to set up the start triggers before changing state
        await asyncio.sleep(0)

        if self.state is not CoreState.starting:
            _LOGGER.warning(
                "Home Assistant startup has been interrupted. "
                "Its state may be inconsistent"
            )
            return

        self.set_state(CoreState.running)
        self.bus.async_fire_internal(EVENT_CORE_CONFIG_UPDATE)
        self.bus.async_fire_internal(EVENT_HOMEASSISTANT_STARTED)

    def add_job[*_Ts](
        self, target: Callable[[*_Ts], Any] | Coroutine[Any, Any, Any], *args: *_Ts
    ) -> None:
        """Add a job to be executed by the event loop or by an executor.

        If the job is either a coroutine or decorated with @callback, it will be
        run by the event loop, if not it will be run by an executor.

        target: target to call.
        args: parameters for method to call.
        """
        if target is None:
            raise ValueError("Don't call add_job with None")
        if asyncio.iscoroutine(target):
            self.loop.call_soon_threadsafe(
                functools.partial(self.async_create_task, target, eager_start=True)
            )
            return
        self.loop.call_soon_threadsafe(
            functools.partial(self._async_add_hass_job, HassJob(target), *args)
        )

    @overload
    @callback
    def async_add_job[_R, *_Ts](
        self,
        target: Callable[[*_Ts], Coroutine[Any, Any, _R]],
        *args: *_Ts,
        eager_start: bool = False,
    ) -> asyncio.Future[_R] | None: ...

    @overload
    @callback
    def async_add_job[_R, *_Ts](
        self,
        target: Callable[[*_Ts], Coroutine[Any, Any, _R] | _R],
        *args: *_Ts,
        eager_start: bool = False,
    ) -> asyncio.Future[_R] | None: ...

    @overload
    @callback
    def async_add_job[_R](
        self,
        target: Coroutine[Any, Any, _R],
        *args: Any,
        eager_start: bool = False,
    ) -> asyncio.Future[_R] | None: ...

    @callback
    def async_add_job[_R, *_Ts](
        self,
        target: Callable[[*_Ts], Coroutine[Any, Any, _R] | _R]
        | Coroutine[Any, Any, _R],
        *args: *_Ts,
        eager_start: bool = False,
    ) -> asyncio.Future[_R] | None:
        """Add a job to be executed by the event loop or by an executor.

        If the job is either a coroutine or decorated with @callback, it will be
        run by the event loop, if not it will be run by an executor.

        This method must be run in the event loop.

        target: target to call.
        args: parameters for method to call.
        """
        # late import to avoid circular imports
        from .helpers import frame  # pylint: disable=import-outside-toplevel

        frame.report_usage(
            "calls `async_add_job`, which should be reviewed against "
            "https://developers.home-assistant.io/blog/2024/03/13/deprecate_add_run_job"
            " for replacement options",
            core_behavior=frame.ReportBehavior.LOG,
            breaks_in_ha_version="2025.4",
        )

        if target is None:
            raise ValueError("Don't call async_add_job with None")

        if asyncio.iscoroutine(target):
            return self.async_create_task(target, eager_start=eager_start)

        return self._async_add_hass_job(HassJob(target), *args)

    @overload
    @callback
    def async_add_hass_job[_R](
        self,
        hassjob: HassJob[..., Coroutine[Any, Any, _R]],
        *args: Any,
        eager_start: bool = False,
        background: bool = False,
    ) -> asyncio.Future[_R] | None: ...

    @overload
    @callback
    def async_add_hass_job[_R](
        self,
        hassjob: HassJob[..., Coroutine[Any, Any, _R] | _R],
        *args: Any,
        eager_start: bool = False,
        background: bool = False,
    ) -> asyncio.Future[_R] | None: ...

    @callback
    def async_add_hass_job[_R](
        self,
        hassjob: HassJob[..., Coroutine[Any, Any, _R] | _R],
        *args: Any,
        eager_start: bool = False,
        background: bool = False,
    ) -> asyncio.Future[_R] | None:
        """Add a HassJob from within the event loop.

        If eager_start is True, coroutine functions will be scheduled eagerly.
        If background is True, the task will created as a background task.

        This method must be run in the event loop.
        hassjob: HassJob to call.
        args: parameters for method to call.
        """
        # late import to avoid circular imports
        from .helpers import frame  # pylint: disable=import-outside-toplevel

        frame.report_usage(
            "calls `async_add_hass_job`, which should be reviewed against "
            "https://developers.home-assistant.io/blog/2024/04/07/deprecate_add_hass_job"
            " for replacement options",
            core_behavior=frame.ReportBehavior.LOG,
            breaks_in_ha_version="2025.5",
        )

        return self._async_add_hass_job(hassjob, *args, background=background)

    @overload
    @callback
    def _async_add_hass_job[_R](
        self,
        hassjob: HassJob[..., Coroutine[Any, Any, _R]],
        *args: Any,
        background: bool = False,
    ) -> asyncio.Future[_R] | None: ...

    @overload
    @callback
    def _async_add_hass_job[_R](
        self,
        hassjob: HassJob[..., Coroutine[Any, Any, _R] | _R],
        *args: Any,
        background: bool = False,
    ) -> asyncio.Future[_R] | None: ...

    @callback
    def _async_add_hass_job[_R](
        self,
        hassjob: HassJob[..., Coroutine[Any, Any, _R] | _R],
        *args: Any,
        background: bool = False,
    ) -> asyncio.Future[_R] | None:
        """Add a HassJob from within the event loop.

        If eager_start is True, coroutine functions will be scheduled eagerly.
        If background is True, the task will created as a background task.

        This method must be run in the event loop.
        hassjob: HassJob to call.
        args: parameters for method to call.
        """
        task: asyncio.Future[_R]
        # This code path is performance sensitive and uses
        # if TYPE_CHECKING to avoid the overhead of constructing
        # the type used for the cast. For history see:
        # https://github.com/home-assistant/core/pull/71960
        if hassjob.job_type is HassJobType.Coroutinefunction:
            if TYPE_CHECKING:
                hassjob = cast(HassJob[..., Coroutine[Any, Any, _R]], hassjob)
            task = create_eager_task(
                hassjob.target(*args), name=hassjob.name, loop=self.loop
            )
            if task.done():
                return task
        elif hassjob.job_type is HassJobType.Callback:
            if TYPE_CHECKING:
                hassjob = cast(HassJob[..., _R], hassjob)
            self.loop.call_soon(hassjob.target, *args)
            return None
        else:
            if TYPE_CHECKING:
                hassjob = cast(HassJob[..., _R], hassjob)
            task = self.loop.run_in_executor(None, hassjob.target, *args)

        task_bucket = self._background_tasks if background else self._tasks
        task_bucket.add(task)
        task.add_done_callback(task_bucket.remove)

        return task

    def create_task(
        self, target: Coroutine[Any, Any, Any], name: str | None = None
    ) -> None:
        """Add task to the executor pool.

        target: target to call.
        """
        self.loop.call_soon_threadsafe(
            functools.partial(
                self.async_create_task_internal, target, name, eager_start=True
            )
        )

    @callback
    def async_create_task[_R](
        self,
        target: Coroutine[Any, Any, _R],
        name: str | None = None,
        eager_start: bool = True,
    ) -> asyncio.Task[_R]:
        """Create a task from within the event loop.

        This method must be run in the event loop. If you are using this in your
        integration, use the create task methods on the config entry instead.

        target: target to call.
        """
        if self.loop_thread_id != threading.get_ident():
            from .helpers import frame  # pylint: disable=import-outside-toplevel

            frame.report_non_thread_safe_operation("hass.async_create_task")
        return self.async_create_task_internal(target, name, eager_start)

    @callback
    def async_create_task_internal[_R](
        self,
        target: Coroutine[Any, Any, _R],
        name: str | None = None,
        eager_start: bool = True,
    ) -> asyncio.Task[_R]:
        """Create a task from within the event loop, internal use only.

        This method is intended to only be used by core internally
        and should not be considered a stable API. We will make
        breaking changes to this function in the future and it
        should not be used in integrations.

        This method must be run in the event loop. If you are using this in your
        integration, use the create task methods on the config entry instead.

        target: target to call.
        """
        if eager_start:
            task = create_eager_task(target, name=name, loop=self.loop)
            if task.done():
                return task
        else:
            # Use loop.create_task
            # to avoid the extra function call in asyncio.create_task.
            task = self.loop.create_task(target, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.remove)
        return task

    @callback
    def async_create_background_task[_R](
        self, target: Coroutine[Any, Any, _R], name: str, eager_start: bool = True
    ) -> asyncio.Task[_R]:
        """Create a task from within the event loop.

        This type of task is for background tasks that usually run for
        the lifetime of Home Assistant or an integration's setup.

        A background task is different from a normal task:

          - Will not block startup
          - Will be automatically cancelled on shutdown
          - Calls to async_block_till_done will not wait for completion

        If you are using this in your integration, use the create task
        methods on the config entry instead.

        This method must be run in the event loop.
        """
        if eager_start:
            task = create_eager_task(target, name=name, loop=self.loop)
            if task.done():
                return task
        else:
            # Use loop.create_task
            # to avoid the extra function call in asyncio.create_task.
            task = self.loop.create_task(target, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.remove)
        return task

    @callback
    def async_add_executor_job[*_Ts, _T](
        self, target: Callable[[*_Ts], _T], *args: *_Ts
    ) -> asyncio.Future[_T]:
        """Add an executor job from within the event loop."""
        task = self.loop.run_in_executor(None, target, *args)

        tracked = asyncio.current_task() in self._tasks
        task_bucket = self._tasks if tracked else self._background_tasks
        task_bucket.add(task)
        task.add_done_callback(task_bucket.remove)

        return task

    @callback
    def async_add_import_executor_job[*_Ts, _T](
        self, target: Callable[[*_Ts], _T], *args: *_Ts
    ) -> asyncio.Future[_T]:
        """Add an import executor job from within the event loop.

        The future returned from this method must be awaited in the event loop.
        """
        return self.loop.run_in_executor(self.import_executor, target, *args)

    @overload
    @callback
    def async_run_hass_job[_R](
        self,
        hassjob: HassJob[..., Coroutine[Any, Any, _R]],
        *args: Any,
        background: bool = False,
    ) -> asyncio.Future[_R] | None: ...

    @overload
    @callback
    def async_run_hass_job[_R](
        self,
        hassjob: HassJob[..., Coroutine[Any, Any, _R] | _R],
        *args: Any,
        background: bool = False,
    ) -> asyncio.Future[_R] | None: ...

    @callback
    def async_run_hass_job[_R](
        self,
        hassjob: HassJob[..., Coroutine[Any, Any, _R] | _R],
        *args: Any,
        background: bool = False,
    ) -> asyncio.Future[_R] | None:
        """Run a HassJob from within the event loop.

        This method must be run in the event loop.

        If background is True, the task will created as a background task.

        hassjob: HassJob
        args: parameters for method to call.
        """
        # This code path is performance sensitive and uses
        # if TYPE_CHECKING to avoid the overhead of constructing
        # the type used for the cast. For history see:
        # https://github.com/home-assistant/core/pull/71960
        if hassjob.job_type is HassJobType.Callback:
            if TYPE_CHECKING:
                hassjob = cast(HassJob[..., _R], hassjob)
            hassjob.target(*args)
            return None

        return self._async_add_hass_job(hassjob, *args, background=background)

    @overload
    @callback
    def async_run_job[_R, *_Ts](
        self, target: Callable[[*_Ts], Coroutine[Any, Any, _R]], *args: *_Ts
    ) -> asyncio.Future[_R] | None: ...

    @overload
    @callback
    def async_run_job[_R, *_Ts](
        self, target: Callable[[*_Ts], Coroutine[Any, Any, _R] | _R], *args: *_Ts
    ) -> asyncio.Future[_R] | None: ...

    @overload
    @callback
    def async_run_job[_R](
        self, target: Coroutine[Any, Any, _R], *args: Any
    ) -> asyncio.Future[_R] | None: ...

    @callback
    def async_run_job[_R, *_Ts](
        self,
        target: Callable[[*_Ts], Coroutine[Any, Any, _R] | _R]
        | Coroutine[Any, Any, _R],
        *args: *_Ts,
    ) -> asyncio.Future[_R] | None:
        """Run a job from within the event loop.

        This method must be run in the event loop.

        target: target to call.
        args: parameters for method to call.
        """
        # late import to avoid circular imports
        from .helpers import frame  # pylint: disable=import-outside-toplevel

        frame.report_usage(
            "calls `async_run_job`, which should be reviewed against "
            "https://developers.home-assistant.io/blog/2024/03/13/deprecate_add_run_job"
            " for replacement options",
            core_behavior=frame.ReportBehavior.LOG,
            breaks_in_ha_version="2025.4",
        )

        if asyncio.iscoroutine(target):
            return self.async_create_task(target, eager_start=True)

        return self.async_run_hass_job(HassJob(target), *args)

    def block_till_done(self, wait_background_tasks: bool = False) -> None:
        """Block until all pending work is done."""
        asyncio.run_coroutine_threadsafe(
            self.async_block_till_done(wait_background_tasks=wait_background_tasks),
            self.loop,
        ).result()

    async def async_block_till_done(self, wait_background_tasks: bool = False) -> None:
        """Block until all pending work is done."""
        # To flush out any call_soon_threadsafe
        await asyncio.sleep(0)
        start_time: float | None = None
        current_task = asyncio.current_task()
        while tasks := [
            task
            for task in (
                self._tasks | self._background_tasks
                if wait_background_tasks
                else self._tasks
            )
            if task is not current_task and not cancelling(task)
        ]:
            await self._await_and_log_pending(tasks)

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
                for task in tasks:
                    _LOGGER.debug("Waiting for task: %s", task)

    async def _await_and_log_pending(
        self, pending: Collection[asyncio.Future[Any]]
    ) -> None:
        """Await and log tasks that take a long time."""
        wait_time = 0
        while pending:
            _, pending = await asyncio.wait(pending, timeout=BLOCK_LOG_TIMEOUT)
            if not pending:
                return
            wait_time += BLOCK_LOG_TIMEOUT
            for task in pending:
                _LOGGER.debug("Waited %s seconds for task: %s", wait_time, task)

    @overload
    @callback
    def async_add_shutdown_job(
        self, hassjob: HassJob[..., Coroutine[Any, Any, Any]], *args: Any
    ) -> CALLBACK_TYPE: ...

    @overload
    @callback
    def async_add_shutdown_job(
        self, hassjob: HassJob[..., Coroutine[Any, Any, Any] | Any], *args: Any
    ) -> CALLBACK_TYPE: ...

    @callback
    def async_add_shutdown_job(
        self, hassjob: HassJob[..., Coroutine[Any, Any, Any] | Any], *args: Any
    ) -> CALLBACK_TYPE:
        """Add a HassJob which will be executed on shutdown.

        This method must be run in the event loop.

        hassjob: HassJob
        args: parameters for method to call.

        Returns function to remove the job.
        """
        job_with_args = HassJobWithArgs(hassjob, args)
        self._shutdown_jobs.append(job_with_args)

        @callback
        def remove_job() -> None:
            self._shutdown_jobs.remove(job_with_args)

        return remove_job

    def stop(self) -> None:
        """Stop Home Assistant and shuts down all threads."""
        if self.state is CoreState.not_running:  # just ignore
            return
        # The future is never retrieved, and we only hold a reference
        # to it to prevent it from being garbage collected.
        self._stop_future = asyncio.run_coroutine_threadsafe(
            self.async_stop(), self.loop
        )

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
            if self.state is CoreState.not_running:  # just ignore
                return
            if self.state in [CoreState.stopping, CoreState.final_write]:
                _LOGGER.info("Additional call to async_stop was ignored")
                return
            if self.state is CoreState.starting:
                # This may not work
                _LOGGER.warning(
                    "Stopping Home Assistant before startup has completed may fail"
                )

        # Stage 1 - Run shutdown jobs
        try:
            async with self.timeout.async_timeout(STOPPING_STAGE_SHUTDOWN_TIMEOUT):
                tasks: list[asyncio.Future[Any]] = []
                for job in self._shutdown_jobs:
                    task_or_none = self.async_run_hass_job(job.job, *job.args)
                    if not task_or_none:
                        continue
                    tasks.append(task_or_none)
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
        except TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for shutdown jobs to complete, the shutdown will"
                " continue"
            )
            self._async_log_running_tasks("run shutdown jobs")

        # Stage 2 - Stop integrations

        # Keep holding the reference to the tasks but do not allow them
        # to block shutdown. Only tasks created after this point will
        # be waited for.
        running_tasks = self._tasks
        # Avoid clearing here since we want the remove callbacks to fire
        # and remove the tasks from the original set which is now running_tasks
        self._tasks = set()

        # Cancel all background tasks
        for task in self._background_tasks:
            self._tasks.add(task)
            task.add_done_callback(self._tasks.remove)
            task.cancel("Home Assistant is stopping")
        self._cancel_cancellable_timers()

        self.exit_code = exit_code

        self.set_state(CoreState.stopping)
        self.bus.async_fire_internal(EVENT_HOMEASSISTANT_STOP)
        try:
            async with self.timeout.async_timeout(STOP_STAGE_SHUTDOWN_TIMEOUT):
                await self.async_block_till_done()
        except TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for integrations to stop, the shutdown will"
                " continue"
            )
            self._async_log_running_tasks("stop integrations")

        # Stage 3 - Final write
        self.set_state(CoreState.final_write)
        self.bus.async_fire_internal(EVENT_HOMEASSISTANT_FINAL_WRITE)
        try:
            async with self.timeout.async_timeout(FINAL_WRITE_STAGE_SHUTDOWN_TIMEOUT):
                await self.async_block_till_done()
        except TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for final writes to complete, the shutdown will"
                " continue"
            )
            self._async_log_running_tasks("final write")

        # Stage 4 - Close
        self.set_state(CoreState.not_running)
        self.bus.async_fire_internal(EVENT_HOMEASSISTANT_CLOSE)

        # Make a copy of running_tasks since a task can finish
        # while we are awaiting canceled tasks to get their result
        # which will result in the set size changing during iteration
        for task in list(running_tasks):
            if task.done() or cancelling(task):
                # Since we made a copy we need to check
                # to see if the task finished while we
                # were awaiting another task
                continue
            _LOGGER.warning(
                "Task %s was still running after final writes shutdown stage; "
                "Integrations should cancel non-critical tasks when receiving "
                "the stop event to prevent delaying shutdown",
                task,
            )
            task.cancel("Home Assistant final writes shutdown stage")
            try:
                async with asyncio.timeout(0.1):
                    await task
            except asyncio.CancelledError:
                pass
            except TimeoutError:
                # Task may be shielded from cancellation.
                _LOGGER.exception(
                    "Task %s could not be canceled during final shutdown stage", task
                )
            except Exception:
                _LOGGER.exception("Task %s error during final shutdown stage", task)

        # Prevent run_callback_threadsafe from scheduling any additional
        # callbacks in the event loop as callbacks created on the futures
        # it returns will never run after the final `self.async_block_till_done`
        # which will cause the futures to block forever when waiting for
        # the `result()` which will cause a deadlock when shutting down the executor.
        shutdown_run_callback_threadsafe(self.loop)

        try:
            async with self.timeout.async_timeout(CLOSE_STAGE_SHUTDOWN_TIMEOUT):
                await self.async_block_till_done()
        except TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for close event to be processed, the shutdown will"
                " continue"
            )
            self._async_log_running_tasks("close")

        self.set_state(CoreState.stopped)
        self.import_executor.shutdown()

        if self._stopped is not None:
            self._stopped.set()

    def _cancel_cancellable_timers(self) -> None:
        """Cancel timer handles marked as cancellable."""
        for handle in get_scheduled_timer_handles(self.loop):
            if (
                not handle.cancelled()
                and (args := handle._args)  # noqa: SLF001
                and type(job := args[0]) is HassJob
                and job.cancel_on_shutdown
            ):
                handle.cancel()

    def _async_log_running_tasks(self, stage: str) -> None:
        """Log all running tasks."""
        for task in self._tasks:
            _LOGGER.warning("Shutdown stage '%s': still running: %s", stage, task)


class Context:
    """The context that triggered something."""

    __slots__ = ("id", "user_id", "parent_id", "origin_event", "_cache")

    def __init__(
        self,
        user_id: str | None = None,
        parent_id: str | None = None,
        id: str | None = None,  # pylint: disable=redefined-builtin
    ) -> None:
        """Init the context."""
        self.id = id or ulid_now()
        self.user_id = user_id
        self.parent_id = parent_id
        self.origin_event: Event[Any] | None = None
        self._cache: dict[str, Any] = {}

    def __eq__(self, other: object) -> bool:
        """Compare contexts."""
        return isinstance(other, Context) and self.id == other.id

    def __copy__(self) -> Context:
        """Create a shallow copy of this context."""
        return Context(user_id=self.user_id, parent_id=self.parent_id, id=self.id)

    def __deepcopy__(self, memo: dict[int, Any]) -> Context:
        """Create a deep copy of this context."""
        return Context(user_id=self.user_id, parent_id=self.parent_id, id=self.id)

    @under_cached_property
    def _as_dict(self) -> dict[str, str | None]:
        """Return a dictionary representation of the context.

        Callers should be careful to not mutate the returned dictionary
        as it will mutate the cached version.
        """
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "user_id": self.user_id,
        }

    def as_dict(self) -> ReadOnlyDict[str, str | None]:
        """Return a ReadOnlyDict representation of the context."""
        return self._as_read_only_dict

    @under_cached_property
    def _as_read_only_dict(self) -> ReadOnlyDict[str, str | None]:
        """Return a ReadOnlyDict representation of the context."""
        return ReadOnlyDict(self._as_dict)

    @under_cached_property
    def json_fragment(self) -> json_fragment:
        """Return a JSON fragment of the context."""
        return json_fragment(json_bytes(self._as_dict))


class EventOrigin(enum.Enum):
    """Represent the origin of an event."""

    local = "LOCAL"
    remote = "REMOTE"

    def __str__(self) -> str:
        """Return the event."""
        return self.value

    @cached_property
    def idx(self) -> int:
        """Return the index of the origin."""
        return next((idx for idx, origin in enumerate(EventOrigin) if origin is self))


class Event(Generic[_DataT]):
    """Representation of an event within the bus."""

    __slots__ = (
        "event_type",
        "data",
        "origin",
        "time_fired_timestamp",
        "context",
        "_cache",
    )

    def __init__(
        self,
        event_type: EventType[_DataT] | str,
        data: _DataT | None = None,
        origin: EventOrigin = EventOrigin.local,
        time_fired_timestamp: float | None = None,
        context: Context | None = None,
    ) -> None:
        """Initialize a new event."""
        self.event_type = event_type
        self.data: _DataT = data or {}  # type: ignore[assignment]
        self.origin = origin
        self.time_fired_timestamp = time_fired_timestamp or time.time()
        if not context:
            context = Context(id=ulid_at_time(self.time_fired_timestamp))
        self.context = context
        if not context.origin_event:
            context.origin_event = self
        self._cache: dict[str, Any] = {}

    @under_cached_property
    def time_fired(self) -> datetime.datetime:
        """Return time fired as a timestamp."""
        return dt_util.utc_from_timestamp(self.time_fired_timestamp)

    @under_cached_property
    def _as_dict(self) -> dict[str, Any]:
        """Create a dict representation of this Event.

        Callers should be careful to not mutate the returned dictionary
        as it will mutate the cached version.
        """
        return {
            "event_type": self.event_type,
            "data": self.data,
            "origin": self.origin.value,
            "time_fired": self.time_fired.isoformat(),
            # _as_dict is marked as protected
            # to avoid callers outside of this module
            # from misusing it by mistake.
            "context": self.context._as_dict,  # noqa: SLF001
        }

    def as_dict(self) -> ReadOnlyDict[str, Any]:
        """Create a ReadOnlyDict representation of this Event.

        Async friendly.
        """
        return self._as_read_only_dict

    @under_cached_property
    def _as_read_only_dict(self) -> ReadOnlyDict[str, Any]:
        """Create a ReadOnlyDict representation of this Event."""
        as_dict = self._as_dict
        data = as_dict["data"]
        context = as_dict["context"]
        # json_fragment will serialize data from a ReadOnlyDict
        # or a normal dict so its ok to have either. We only
        # mutate the cache if someone asks for the as_dict version
        # to avoid storing multiple copies of the data in memory.
        if type(data) is not ReadOnlyDict:
            as_dict["data"] = ReadOnlyDict(data)
        if type(context) is not ReadOnlyDict:
            as_dict["context"] = ReadOnlyDict(context)
        return ReadOnlyDict(as_dict)

    @under_cached_property
    def json_fragment(self) -> json_fragment:
        """Return an event as a JSON fragment."""
        return json_fragment(json_bytes(self._as_dict))

    def __repr__(self) -> str:
        """Return the representation."""
        return _event_repr(self.event_type, self.origin, self.data)


def _event_repr(
    event_type: EventType[_DataT] | str, origin: EventOrigin, data: _DataT | None
) -> str:
    """Return the representation."""
    if data:
        return f"<Event {event_type}[{str(origin)[0]}]: {util.repr_helper(data)}>"

    return f"<Event {event_type}[{str(origin)[0]}]>"


_FilterableJobType = tuple[
    HassJob[[Event[_DataT]], Coroutine[Any, Any, None] | None],  # job
    Callable[[_DataT], bool] | None,  # event_filter
]


@dataclass(slots=True)
class _OneTimeListener(Generic[_DataT]):
    hass: HomeAssistant
    listener_job: HassJob[[Event[_DataT]], Coroutine[Any, Any, None] | None]
    remove: CALLBACK_TYPE | None = None

    @callback
    def __call__(self, event: Event[_DataT]) -> None:
        """Remove listener from event bus and then fire listener."""
        if not self.remove:
            # If the listener was already removed, we don't need to do anything
            return
        self.remove()
        self.remove = None
        self.hass.async_run_hass_job(self.listener_job, event)

    def __repr__(self) -> str:
        """Return the representation of the listener and source module."""
        module = inspect.getmodule(self.listener_job.target)
        if module:
            return f"<_OneTimeListener {module.__name__}:{self.listener_job.target}>"
        return f"<_OneTimeListener {self.listener_job.target}>"


# Empty list, used by EventBus.async_fire_internal
EMPTY_LIST: list[Any] = []


@functools.lru_cache
def _verify_event_type_length_or_raise(event_type: EventType[_DataT] | str) -> None:
    """Verify the length of the event type and raise if too long."""
    if len(event_type) > MAX_LENGTH_EVENT_EVENT_TYPE:
        raise MaxLengthExceeded(event_type, "event_type", MAX_LENGTH_EVENT_EVENT_TYPE)


class EventBus:
    """Allow the firing of and listening for events."""

    __slots__ = ("_debug", "_hass", "_listeners", "_match_all_listeners")

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a new event bus."""
        self._listeners: defaultdict[
            EventType[Any] | str, list[_FilterableJobType[Any]]
        ] = defaultdict(list)
        self._match_all_listeners: list[_FilterableJobType[Any]] = []
        self._listeners[MATCH_ALL] = self._match_all_listeners
        self._hass = hass
        self._async_logging_changed()
        self.async_listen(EVENT_LOGGING_CHANGED, self._async_logging_changed)

    @callback
    def _async_logging_changed(self, event: Event | None = None) -> None:
        """Handle logging change."""
        self._debug = _LOGGER.isEnabledFor(logging.DEBUG)

    @callback
    def async_listeners(self) -> dict[EventType[Any] | str, int]:
        """Return dictionary with events and the number of listeners.

        This method must be run in the event loop.
        """
        return {key: len(listeners) for key, listeners in self._listeners.items()}

    @property
    def listeners(self) -> dict[EventType[Any] | str, int]:
        """Return dictionary with events and the number of listeners."""
        return run_callback_threadsafe(self._hass.loop, self.async_listeners).result()

    def fire(
        self,
        event_type: EventType[_DataT] | str,
        event_data: _DataT | None = None,
        origin: EventOrigin = EventOrigin.local,
        context: Context | None = None,
    ) -> None:
        """Fire an event."""
        _verify_event_type_length_or_raise(event_type)
        self._hass.loop.call_soon_threadsafe(
            self.async_fire_internal, event_type, event_data, origin, context
        )

    @callback
    def async_fire(
        self,
        event_type: EventType[_DataT] | str,
        event_data: _DataT | None = None,
        origin: EventOrigin = EventOrigin.local,
        context: Context | None = None,
        time_fired: float | None = None,
    ) -> None:
        """Fire an event.

        This method must be run in the event loop.
        """
        _verify_event_type_length_or_raise(event_type)
        if self._hass.loop_thread_id != threading.get_ident():
            from .helpers import frame  # pylint: disable=import-outside-toplevel

            frame.report_non_thread_safe_operation("hass.bus.async_fire")
        return self.async_fire_internal(
            event_type, event_data, origin, context, time_fired
        )

    @callback
    def async_fire_internal(
        self,
        event_type: EventType[_DataT] | str,
        event_data: _DataT | None = None,
        origin: EventOrigin = EventOrigin.local,
        context: Context | None = None,
        time_fired: float | None = None,
    ) -> None:
        """Fire an event, for internal use only.

        This method is intended to only be used by core internally
        and should not be considered a stable API. We will make
        breaking changes to this function in the future and it
        should not be used in integrations.

        This method must be run in the event loop.
        """
        if self._debug:
            _LOGGER.debug(
                "Bus:Handling %s", _event_repr(event_type, origin, event_data)
            )

        listeners = self._listeners.get(event_type, EMPTY_LIST)
        if event_type not in EVENTS_EXCLUDED_FROM_MATCH_ALL:
            match_all_listeners = self._match_all_listeners
        else:
            match_all_listeners = EMPTY_LIST

        event: Event[_DataT] | None = None
        for job, event_filter in listeners + match_all_listeners:
            if event_filter is not None:
                try:
                    if event_data is None or not event_filter(event_data):
                        continue
                except Exception:
                    _LOGGER.exception("Error in event filter")
                    continue

            if not event:
                event = Event(
                    event_type,
                    event_data,
                    origin,
                    time_fired,
                    context,
                )

            try:
                self._hass.async_run_hass_job(job, event)
            except Exception:
                _LOGGER.exception("Error running job: %s", job)

    def listen(
        self,
        event_type: EventType[_DataT] | str,
        listener: Callable[[Event[_DataT]], Coroutine[Any, Any, None] | None],
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
        event_type: EventType[_DataT] | str,
        listener: Callable[[Event[_DataT]], Coroutine[Any, Any, None] | None],
        event_filter: Callable[[_DataT], bool] | None = None,
        run_immediately: bool | object = _SENTINEL,
    ) -> CALLBACK_TYPE:
        """Listen for all events or events of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        An optional event_filter, which must be a callable decorated with
        @callback that returns a boolean value, determines if the
        listener callable should run.

        If run_immediately is passed:
          - callbacks will be run right away instead of using call_soon.
          - coroutine functions will be scheduled eagerly.

        This method must be run in the event loop.
        """
        if run_immediately in (True, False):
            # late import to avoid circular imports
            from .helpers import frame  # pylint: disable=import-outside-toplevel

            frame.report_usage(
                "calls `async_listen` with run_immediately",
                core_behavior=frame.ReportBehavior.LOG,
                breaks_in_ha_version="2025.5",
            )

        if event_filter is not None and not is_callback_check_partial(event_filter):
            raise HomeAssistantError(f"Event filter {event_filter} is not a callback")
        filterable_job = (HassJob(listener, f"listen {event_type}"), event_filter)
        if event_type == EVENT_STATE_REPORTED:
            if not event_filter:
                raise HomeAssistantError(
                    f"Event filter is required for event {event_type}"
                )
        return self._async_listen_filterable_job(event_type, filterable_job)

    @callback
    def _async_listen_filterable_job(
        self,
        event_type: EventType[_DataT] | str,
        filterable_job: _FilterableJobType[_DataT],
    ) -> CALLBACK_TYPE:
        """Listen for all events or events of a specific type."""
        self._listeners[event_type].append(filterable_job)
        return functools.partial(
            self._async_remove_listener, event_type, filterable_job
        )

    def listen_once(
        self,
        event_type: EventType[_DataT] | str,
        listener: Callable[[Event[_DataT]], Coroutine[Any, Any, None] | None],
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
        event_type: EventType[_DataT] | str,
        listener: Callable[[Event[_DataT]], Coroutine[Any, Any, None] | None],
        run_immediately: bool | object = _SENTINEL,
    ) -> CALLBACK_TYPE:
        """Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Returns registered listener that can be used with remove_listener.

        This method must be run in the event loop.
        """
        if run_immediately in (True, False):
            # late import to avoid circular imports
            from .helpers import frame  # pylint: disable=import-outside-toplevel

            frame.report_usage(
                "calls `async_listen_once` with run_immediately",
                core_behavior=frame.ReportBehavior.LOG,
                breaks_in_ha_version="2025.5",
            )

        one_time_listener: _OneTimeListener[_DataT] = _OneTimeListener(
            self._hass, HassJob(listener)
        )
        remove = self._async_listen_filterable_job(
            event_type,
            (
                HassJob(
                    one_time_listener,
                    f"onetime listen {event_type} {listener}",
                    job_type=HassJobType.Callback,
                ),
                None,
            ),
        )
        one_time_listener.remove = remove
        return remove

    @callback
    def _async_remove_listener(
        self,
        event_type: EventType[_DataT] | str,
        filterable_job: _FilterableJobType[_DataT],
    ) -> None:
        """Remove a listener of a specific event_type.

        This method must be run in the event loop.
        """
        try:
            self._listeners[event_type].remove(filterable_job)

            # delete event_type list if empty
            if not self._listeners[event_type] and event_type != MATCH_ALL:
                self._listeners.pop(event_type)
        except (KeyError, ValueError):
            # KeyError is key event_type listener did not exist
            # ValueError if listener did not exist within event_type
            _LOGGER.exception(
                "Unable to remove unknown job listener %s", filterable_job
            )


class CompressedState(TypedDict):
    """Compressed dict of a state."""

    s: str  # COMPRESSED_STATE_STATE
    a: ReadOnlyDict[str, Any]  # COMPRESSED_STATE_ATTRIBUTES
    c: str | dict[str, Any]  # COMPRESSED_STATE_CONTEXT
    lc: float  # COMPRESSED_STATE_LAST_CHANGED
    lu: NotRequired[float]  # COMPRESSED_STATE_LAST_UPDATED


class State:
    """Object to represent a state within the state machine.

    entity_id: the entity that is represented.
    state: the state of the entity
    attributes: extra information on entity and state
    last_changed: last time the state was changed.
    last_reported: last time the state was reported.
    last_updated: last time the state or attributes were changed.
    context: Context in which it was created
    domain: Domain of this state.
    object_id: Object id of this state.
    """

    __slots__ = (
        "entity_id",
        "state",
        "attributes",
        "last_changed",
        "last_reported",
        "last_updated",
        "context",
        "state_info",
        "domain",
        "object_id",
        "last_updated_timestamp",
        "_cache",
    )

    def __init__(
        self,
        entity_id: str,
        state: str,
        attributes: Mapping[str, Any] | None = None,
        last_changed: datetime.datetime | None = None,
        last_reported: datetime.datetime | None = None,
        last_updated: datetime.datetime | None = None,
        context: Context | None = None,
        validate_entity_id: bool | None = True,
        state_info: StateInfo | None = None,
        last_updated_timestamp: float | None = None,
    ) -> None:
        """Initialize a new state."""
        self._cache: dict[str, Any] = {}
        state = str(state)

        if validate_entity_id and not valid_entity_id(entity_id):
            raise InvalidEntityFormatError(
                f"Invalid entity id encountered: {entity_id}. "
                "Format should be <domain>.<object_id>"
            )

        validate_state(state)

        self.entity_id = entity_id
        self.state = state
        # State only creates and expects a ReadOnlyDict so
        # there is no need to check for subclassing with
        # isinstance here so we can use the faster type check.
        if type(attributes) is not ReadOnlyDict:
            self.attributes = ReadOnlyDict(attributes or {})
        else:
            self.attributes = attributes
        self.last_reported = last_reported or dt_util.utcnow()
        self.last_updated = last_updated or self.last_reported
        self.last_changed = last_changed or self.last_updated
        self.context = context or Context()
        self.state_info = state_info
        self.domain, self.object_id = split_entity_id(self.entity_id)
        # The recorder or the websocket_api will always call the timestamps,
        # so we will set the timestamp values here to avoid the overhead of
        # the function call in the property we know will always be called.
        last_updated = self.last_updated
        if not last_updated_timestamp:
            last_updated_timestamp = last_updated.timestamp()
        self.last_updated_timestamp = last_updated_timestamp
        if self.last_changed == last_updated:
            self._cache["last_changed_timestamp"] = last_updated_timestamp
        # If last_reported is the same as last_updated async_set will pass
        # the same datetime object for both values so we can use an identity
        # check here.
        if self.last_reported is last_updated:
            self._cache["last_reported_timestamp"] = last_updated_timestamp

    @under_cached_property
    def name(self) -> str:
        """Name of this state."""
        return self.attributes.get(ATTR_FRIENDLY_NAME) or self.object_id.replace(
            "_", " "
        )

    @under_cached_property
    def last_changed_timestamp(self) -> float:
        """Timestamp of last change."""
        return self.last_changed.timestamp()

    @under_cached_property
    def last_reported_timestamp(self) -> float:
        """Timestamp of last report."""
        return self.last_reported.timestamp()

    @under_cached_property
    def _as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the State.

        Callers should be careful to not mutate the returned dictionary
        as it will mutate the cached version.
        """
        last_changed_isoformat = self.last_changed.isoformat()
        if self.last_changed == self.last_updated:
            last_updated_isoformat = last_changed_isoformat
        else:
            last_updated_isoformat = self.last_updated.isoformat()
        if self.last_changed == self.last_reported:
            last_reported_isoformat = last_changed_isoformat
        else:
            last_reported_isoformat = self.last_reported.isoformat()
        return {
            "entity_id": self.entity_id,
            "state": self.state,
            "attributes": self.attributes,
            "last_changed": last_changed_isoformat,
            "last_reported": last_reported_isoformat,
            "last_updated": last_updated_isoformat,
            # _as_dict is marked as protected
            # to avoid callers outside of this module
            # from misusing it by mistake.
            "context": self.context._as_dict,  # noqa: SLF001
        }

    def as_dict(
        self,
    ) -> ReadOnlyDict[str, datetime.datetime | Collection[Any]]:
        """Return a ReadOnlyDict representation of the State.

        Async friendly.

        Can be used for JSON serialization.
        Ensures: state == State.from_dict(state.as_dict())
        """
        return self._as_read_only_dict

    @under_cached_property
    def _as_read_only_dict(
        self,
    ) -> ReadOnlyDict[str, datetime.datetime | Collection[Any]]:
        """Return a ReadOnlyDict representation of the State."""
        as_dict = self._as_dict
        context = as_dict["context"]
        # json_fragment will serialize data from a ReadOnlyDict
        # or a normal dict so its ok to have either. We only
        # mutate the cache if someone asks for the as_dict version
        # to avoid storing multiple copies of the data in memory.
        if type(context) is not ReadOnlyDict:
            as_dict["context"] = ReadOnlyDict(context)
        return ReadOnlyDict(as_dict)

    @under_cached_property
    def as_dict_json(self) -> bytes:
        """Return a JSON string of the State."""
        return json_bytes(self._as_dict)

    @under_cached_property
    def json_fragment(self) -> json_fragment:
        """Return a JSON fragment of the State."""
        return json_fragment(self.as_dict_json)

    @under_cached_property
    def as_compressed_state(self) -> CompressedState:
        """Build a compressed dict of a state for adds.

        Omits the lu (last_updated) if it matches (lc) last_changed.

        Sends c (context) as a string if it only contains an id.
        """
        state_context = self.context
        if state_context.parent_id is None and state_context.user_id is None:
            context: dict[str, Any] | str = state_context.id
        else:
            # _as_dict is marked as protected
            # to avoid callers outside of this module
            # from misusing it by mistake.
            context = state_context._as_dict  # noqa: SLF001
        compressed_state: CompressedState = {
            COMPRESSED_STATE_STATE: self.state,
            COMPRESSED_STATE_ATTRIBUTES: self.attributes,
            COMPRESSED_STATE_CONTEXT: context,
            COMPRESSED_STATE_LAST_CHANGED: self.last_changed_timestamp,
        }
        if self.last_changed != self.last_updated:
            compressed_state[COMPRESSED_STATE_LAST_UPDATED] = (
                self.last_updated_timestamp
            )
        return compressed_state

    @under_cached_property
    def as_compressed_state_json(self) -> bytes:
        """Build a compressed JSON key value pair of a state for adds.

        The JSON string is a key value pair of the entity_id and the compressed state.

        It is used for sending multiple states in a single message.
        """
        return json_bytes({self.entity_id: self.as_compressed_state})[1:-1]

    @classmethod
    def from_dict(cls, json_dict: dict[str, Any]) -> Self | None:
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

        last_reported = json_dict.get("last_reported")
        if isinstance(last_reported, str):
            last_reported = dt_util.parse_datetime(last_reported)

        if context := json_dict.get("context"):
            context = Context(id=context.get("id"), user_id=context.get("user_id"))

        return cls(
            json_dict["entity_id"],
            json_dict["state"],
            json_dict.get("attributes"),
            last_changed=last_changed,
            last_reported=last_reported,
            last_updated=last_updated,
            context=context,
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

    def __repr__(self) -> str:
        """Return the representation of the states."""
        attrs = f"; {util.repr_helper(self.attributes)}" if self.attributes else ""

        return (
            f"<state {self.entity_id}={self.state}{attrs}"
            f" @ {dt_util.as_local(self.last_changed).isoformat()}>"
        )


class States(UserDict[str, State]):
    """Container for states, maps entity_id -> State.

    Maintains an additional index:
    - domain -> dict[str, State]
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._domain_index: defaultdict[str, dict[str, State]] = defaultdict(dict)

    def values(self) -> ValuesView[State]:
        """Return the underlying values to avoid __iter__ overhead."""
        return self.data.values()

    def __setitem__(self, key: str, entry: State) -> None:
        """Add an item."""
        self.data[key] = entry
        self._domain_index[entry.domain][entry.entity_id] = entry

    def __delitem__(self, key: str) -> None:
        """Remove an item."""
        entry = self[key]
        del self._domain_index[entry.domain][entry.entity_id]
        super().__delitem__(key)

    def domain_entity_ids(self, key: str) -> KeysView[str] | tuple[()]:
        """Get all entity_ids for a domain."""
        # Avoid polluting _domain_index with non-existing domains
        if key not in self._domain_index:
            return ()
        return self._domain_index[key].keys()

    def domain_states(self, key: str) -> ValuesView[State] | tuple[()]:
        """Get all states for a domain."""
        # Avoid polluting _domain_index with non-existing domains
        if key not in self._domain_index:
            return ()
        return self._domain_index[key].values()


class StateMachine:
    """Helper class that tracks the state of different entities."""

    __slots__ = ("_states", "_states_data", "_reservations", "_bus", "_loop")

    def __init__(self, bus: EventBus, loop: asyncio.events.AbstractEventLoop) -> None:
        """Initialize state machine."""
        self._states = States()
        # _states_data is used to access the States backing dict directly to speed
        # up read operations
        self._states_data = self._states.data
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
            return list(self._states_data)

        if isinstance(domain_filter, str):
            return list(self._states.domain_entity_ids(domain_filter.lower()))

        entity_ids: list[str] = []
        for domain in domain_filter:
            entity_ids.extend(self._states.domain_entity_ids(domain))
        return entity_ids

    @callback
    def async_entity_ids_count(
        self, domain_filter: str | Iterable[str] | None = None
    ) -> int:
        """Count the entity ids that are being tracked.

        This method must be run in the event loop.
        """
        if domain_filter is None:
            return len(self._states_data)

        if isinstance(domain_filter, str):
            return len(self._states.domain_entity_ids(domain_filter.lower()))

        return sum(
            len(self._states.domain_entity_ids(domain)) for domain in domain_filter
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
            return list(self._states_data.values())

        if isinstance(domain_filter, str):
            return list(self._states.domain_states(domain_filter.lower()))

        states: list[State] = []
        for domain in domain_filter:
            states.extend(self._states.domain_states(domain))
        return states

    def get(self, entity_id: str) -> State | None:
        """Retrieve state of entity_id or None if not found.

        Async friendly.
        """
        return self._states_data.get(entity_id) or self._states_data.get(
            entity_id.lower()
        )

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
        self._reservations.discard(entity_id)

        if old_state is None:
            return False

        old_state.expire()
        state_changed_data: EventStateChangedData = {
            "entity_id": entity_id,
            "old_state": old_state,
            "new_state": None,
        }
        self._bus.async_fire_internal(
            EVENT_STATE_CHANGED,
            state_changed_data,
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
        if entity_id in self._states_data or entity_id in self._reservations:
            raise HomeAssistantError(
                "async_reserve must not be called once the state is in the state"
                " machine."
            )

        self._reservations.add(entity_id)

    @callback
    def async_available(self, entity_id: str) -> bool:
        """Check to see if an entity_id is available to be used."""
        entity_id = entity_id.lower()
        return (
            entity_id not in self._states_data and entity_id not in self._reservations
        )

    @callback
    def async_set(
        self,
        entity_id: str,
        new_state: str,
        attributes: Mapping[str, Any] | None = None,
        force_update: bool = False,
        context: Context | None = None,
        state_info: StateInfo | None = None,
        timestamp: float | None = None,
    ) -> None:
        """Set the state of an entity, add entity if it does not exist.

        Attributes is an optional dict to specify attributes of this state.

        If you just update the attributes and not the state, last changed will
        not be affected.

        This method must be run in the event loop.
        """
        self.async_set_internal(
            entity_id.lower(),
            str(new_state),
            attributes or {},
            force_update,
            context,
            state_info,
            timestamp or time.time(),
        )

    @callback
    def async_set_internal(
        self,
        entity_id: str,
        new_state: str,
        attributes: Mapping[str, Any] | None,
        force_update: bool,
        context: Context | None,
        state_info: StateInfo | None,
        timestamp: float,
    ) -> None:
        """Set the state of an entity, add entity if it does not exist.

        This method is intended to only be used by core internally
        and should not be considered a stable API. We will make
        breaking changes to this function in the future and it
        should not be used in integrations.

        This method must be run in the event loop.
        """
        # Most cases the key will be in the dict
        # so we optimize for the happy path as
        # python 3.11+ has near zero overhead for
        # try when it does not raise an exception.
        old_state: State | None
        try:
            old_state = self._states_data[entity_id]
        except KeyError:
            old_state = None
            same_state = False
            same_attr = False
            last_changed = None
        else:
            same_state = old_state.state == new_state and not force_update
            same_attr = old_state.attributes == attributes
            last_changed = old_state.last_changed if same_state else None

        # It is much faster to convert a timestamp to a utc datetime object
        # than converting a utc datetime object to a timestamp since cpython
        # does not have a fast path for handling the UTC timezone and has to do
        # multiple local timezone conversions.
        #
        # from_timestamp implementation:
        # https://github.com/python/cpython/blob/c90a862cdcf55dc1753c6466e5fa4a467a13ae24/Modules/_datetimemodule.c#L2936
        #
        # timestamp implementation:
        # https://github.com/python/cpython/blob/c90a862cdcf55dc1753c6466e5fa4a467a13ae24/Modules/_datetimemodule.c#L6387
        # https://github.com/python/cpython/blob/c90a862cdcf55dc1753c6466e5fa4a467a13ae24/Modules/_datetimemodule.c#L6323
        now = dt_util.utc_from_timestamp(timestamp)

        if context is None:
            context = Context(id=ulid_at_time(timestamp))

        if same_state and same_attr:
            # mypy does not understand this is only possible if old_state is not None
            old_last_reported = old_state.last_reported  # type: ignore[union-attr]
            old_state.last_reported = now  # type: ignore[union-attr]
            old_state._cache["last_reported_timestamp"] = timestamp  # type: ignore[union-attr] # noqa: SLF001
            # Avoid creating an EventStateReportedData
            self._bus.async_fire_internal(  # type: ignore[misc]
                EVENT_STATE_REPORTED,
                {
                    "entity_id": entity_id,
                    "old_last_reported": old_last_reported,
                    "new_state": old_state,
                },
                context=context,
                time_fired=timestamp,
            )
            return

        if same_attr:
            if TYPE_CHECKING:
                assert old_state is not None
            attributes = old_state.attributes

        # This is intentionally called with positional only arguments for performance
        # reasons
        state = State(
            entity_id,
            new_state,
            attributes,
            last_changed,
            now,
            now,
            context,
            old_state is None,
            state_info,
            timestamp,
        )
        if old_state is not None:
            old_state.expire()
        self._states[entity_id] = state
        state_changed_data: EventStateChangedData = {
            "entity_id": entity_id,
            "old_state": old_state,
            "new_state": state,
        }
        self._bus.async_fire_internal(
            EVENT_STATE_CHANGED,
            state_changed_data,
            context=context,
            time_fired=timestamp,
        )


class SupportsResponse(enum.StrEnum):
    """Service call response configuration."""

    NONE = "none"
    """The service does not support responses (the default)."""

    OPTIONAL = "optional"
    """The service optionally returns response data when asked by the caller."""

    ONLY = "only"
    """The service is read-only and the caller must always ask for response data."""


class Service:
    """Representation of a callable service."""

    __slots__ = ["job", "schema", "domain", "service", "supports_response"]

    def __init__(
        self,
        func: Callable[
            [ServiceCall],
            Coroutine[Any, Any, ServiceResponse | EntityServiceResponse]
            | ServiceResponse
            | EntityServiceResponse
            | None,
        ],
        schema: VolSchemaType | None,
        domain: str,
        service: str,
        context: Context | None = None,
        supports_response: SupportsResponse = SupportsResponse.NONE,
        job_type: HassJobType | None = None,
    ) -> None:
        """Initialize a service."""
        self.job = HassJob(func, f"service {domain}.{service}", job_type=job_type)
        self.schema = schema
        self.supports_response = supports_response


class ServiceCall:
    """Representation of a call to a service."""

    __slots__ = ("hass", "domain", "service", "data", "context", "return_response")

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        service: str,
        data: dict[str, Any] | None = None,
        context: Context | None = None,
        return_response: bool = False,
    ) -> None:
        """Initialize a service call."""
        self.hass = hass
        self.domain = domain
        self.service = service
        self.data = ReadOnlyDict(data or {})
        self.context = context or Context()
        self.return_response = return_response

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

    __slots__ = ("_services", "_hass")

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

        This method makes a copy of the registry. This function is expensive,
        and should only be used if has_service is not sufficient.

        This method must be run in the event loop.
        """
        return {domain: service.copy() for domain, service in self._services.items()}

    @callback
    def async_services_for_domain(self, domain: str) -> dict[str, Service]:
        """Return dictionary with per domain a list of available services.

        This method makes a copy of the registry for the domain.

        This method must be run in the event loop.
        """
        return self._services.get(domain, {}).copy()

    @callback
    def async_services_internal(self) -> dict[str, dict[str, Service]]:
        """Return dictionary with per domain a list of available services.

        This method DOES NOT make a copy of the services like async_services does.
        It is only expected to be called from the Home Assistant internals
        as a performance optimization when the caller is not going to modify the
        returned data.

        This method must be run in the event loop.
        """
        return self._services

    def has_service(self, domain: str, service: str) -> bool:
        """Test if specified service exists.

        Async friendly.
        """
        return service.lower() in self._services.get(domain.lower(), [])

    def supports_response(self, domain: str, service: str) -> SupportsResponse:
        """Return whether or not the service supports response data.

        This exists so that callers can return more helpful error messages given
        the context. Will return NONE if the service does not exist as there is
        other error handling when calling the service if it does not exist.
        """
        if not (handler := self._services[domain.lower()][service.lower()]):
            return SupportsResponse.NONE
        return handler.supports_response

    def register(
        self,
        domain: str,
        service: str,
        service_func: Callable[
            [ServiceCall],
            Coroutine[Any, Any, ServiceResponse] | ServiceResponse | None,
        ],
        schema: vol.Schema | None = None,
        supports_response: SupportsResponse = SupportsResponse.NONE,
    ) -> None:
        """Register a service.

        Schema is called to coerce and validate the service data.
        """
        run_callback_threadsafe(
            self._hass.loop,
            self._async_register,
            domain,
            service,
            service_func,
            schema,
            supports_response,
        ).result()

    @callback
    def async_register(
        self,
        domain: str,
        service: str,
        service_func: Callable[
            [ServiceCall],
            Coroutine[Any, Any, ServiceResponse | EntityServiceResponse]
            | ServiceResponse
            | EntityServiceResponse
            | None,
        ],
        schema: VolSchemaType | None = None,
        supports_response: SupportsResponse = SupportsResponse.NONE,
        job_type: HassJobType | None = None,
    ) -> None:
        """Register a service.

        Schema is called to coerce and validate the service data.

        This method must be run in the event loop.
        """
        self._hass.verify_event_loop_thread("hass.services.async_register")
        self._async_register(
            domain, service, service_func, schema, supports_response, job_type
        )

    @callback
    def _async_register(
        self,
        domain: str,
        service: str,
        service_func: Callable[
            [ServiceCall],
            Coroutine[Any, Any, ServiceResponse | EntityServiceResponse]
            | ServiceResponse
            | EntityServiceResponse
            | None,
        ],
        schema: VolSchemaType | None = None,
        supports_response: SupportsResponse = SupportsResponse.NONE,
        job_type: HassJobType | None = None,
    ) -> None:
        """Register a service.

        Schema is called to coerce and validate the service data.

        This method must be run in the event loop.
        """
        domain = domain.lower()
        service = service.lower()
        service_obj = Service(
            service_func,
            schema,
            domain,
            service,
            supports_response=supports_response,
            job_type=job_type,
        )

        if domain in self._services:
            self._services[domain][service] = service_obj
        else:
            self._services[domain] = {service: service_obj}

        self._hass.bus.async_fire_internal(
            EVENT_SERVICE_REGISTERED, {ATTR_DOMAIN: domain, ATTR_SERVICE: service}
        )

    def remove(self, domain: str, service: str) -> None:
        """Remove a registered service from service handler."""
        run_callback_threadsafe(
            self._hass.loop, self._async_remove, domain, service
        ).result()

    @callback
    def async_remove(self, domain: str, service: str) -> None:
        """Remove a registered service from service handler.

        This method must be run in the event loop.
        """
        self._hass.verify_event_loop_thread("hass.services.async_remove")
        self._async_remove(domain, service)

    @callback
    def _async_remove(self, domain: str, service: str) -> None:
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

        self._hass.bus.async_fire_internal(
            EVENT_SERVICE_REMOVED, {ATTR_DOMAIN: domain, ATTR_SERVICE: service}
        )

    def call(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        blocking: bool = False,
        context: Context | None = None,
        target: dict[str, Any] | None = None,
        return_response: bool = False,
    ) -> ServiceResponse:
        """Call a service.

        See description of async_call for details.
        """
        return asyncio.run_coroutine_threadsafe(
            self.async_call(
                domain,
                service,
                service_data,
                blocking,
                context,
                target,
                return_response,
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
        target: dict[str, Any] | None = None,
        return_response: bool = False,
    ) -> ServiceResponse:
        """Call a service.

        Specify blocking=True to wait until service is executed.

        If return_response=True, indicates that the caller can consume return values
        from the service, if any. Return values are a dict that can be returned by the
        standard JSON serialization process. Return values can only be used with blocking=True.

        This method will fire an event to indicate the service has been called.

        Because the service is sent as an event you are not allowed to use
        the keys ATTR_DOMAIN and ATTR_SERVICE in your service_data.

        This method is a coroutine.
        """
        context = context or Context()
        service_data = service_data or {}

        try:
            handler = self._services[domain][service]
        except KeyError:
            # Almost all calls are already lower case, so we avoid
            # calling lower() on the arguments in the common case.
            domain = domain.lower()
            service = service.lower()
            try:
                handler = self._services[domain][service]
            except KeyError:
                raise ServiceNotFound(domain, service) from None

        if return_response:
            if not blocking:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="service_should_be_blocking",
                    translation_placeholders={
                        "return_response": "return_response=True",
                        "non_blocking_argument": "blocking=False",
                    },
                )
            if handler.supports_response is SupportsResponse.NONE:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="service_does_not_support_response",
                    translation_placeholders={
                        "return_response": "return_response=True"
                    },
                )
        elif handler.supports_response is SupportsResponse.ONLY:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_lacks_response_request",
                translation_placeholders={"return_response": "return_response=True"},
            )

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

        service_call = ServiceCall(
            self._hass, domain, service, processed_data, context, return_response
        )

        self._hass.bus.async_fire_internal(
            EVENT_CALL_SERVICE,
            {
                ATTR_DOMAIN: domain,
                ATTR_SERVICE: service,
                ATTR_SERVICE_DATA: service_data,
            },
            context=context,
        )

        coro = self._execute_service(handler, service_call)
        if not blocking:
            self._hass.async_create_task_internal(
                self._run_service_call_catch_exceptions(coro, service_call),
                f"service call background {service_call.domain}.{service_call.service}",
                eager_start=True,
            )
            return None

        response_data = await coro
        if not return_response:
            return None
        if not isinstance(response_data, dict):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_reponse_invalid",
                translation_placeholders={
                    "response_data_type": str(type(response_data))
                },
            )
        return response_data

    async def _run_service_call_catch_exceptions(
        self,
        coro_or_task: Coroutine[Any, Any, Any] | asyncio.Task[Any],
        service_call: ServiceCall,
    ) -> None:
        """Run service call in background, catching and logging any exceptions."""
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
        except Exception:
            _LOGGER.exception("Error executing service: %s", service_call)

    async def _execute_service(
        self, handler: Service, service_call: ServiceCall
    ) -> ServiceResponse:
        """Execute a service."""
        job = handler.job
        target = job.target
        if job.job_type is HassJobType.Coroutinefunction:
            if TYPE_CHECKING:
                target = cast(
                    Callable[..., Coroutine[Any, Any, ServiceResponse]], target
                )
            return await target(service_call)
        if job.job_type is HassJobType.Callback:
            if TYPE_CHECKING:
                target = cast(Callable[..., ServiceResponse], target)
            return target(service_call)
        if TYPE_CHECKING:
            target = cast(Callable[..., ServiceResponse], target)
        return await self._hass.async_add_executor_job(target, service_call)


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = functools.partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = functools.partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
