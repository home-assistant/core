"""Manage config entries in Home Assistant."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Generator, Iterable, Mapping
from contextvars import ContextVar
from copy import deepcopy
from enum import Enum, StrEnum
import functools
import logging
from random import randint
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from . import data_entry_flow, loader
from .components import persistent_notification
from .const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP, Platform
from .core import CALLBACK_TYPE, CoreState, Event, HassJob, HomeAssistant, callback
from .data_entry_flow import FlowResult
from .exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from .helpers import device_registry, entity_registry, storage
from .helpers.debounce import Debouncer
from .helpers.dispatcher import async_dispatcher_send
from .helpers.event import (
    RANDOM_MICROSECOND_MAX,
    RANDOM_MICROSECOND_MIN,
    async_call_later,
)
from .helpers.frame import report
from .helpers.typing import UNDEFINED, ConfigType, DiscoveryInfoType, UndefinedType
from .setup import DATA_SETUP_DONE, async_process_deps_reqs, async_setup_component
from .util import uuid as uuid_util
from .util.decorator import Registry

if TYPE_CHECKING:
    from .components.bluetooth import BluetoothServiceInfoBleak
    from .components.dhcp import DhcpServiceInfo
    from .components.hassio import HassioServiceInfo
    from .components.ssdp import SsdpServiceInfo
    from .components.usb import UsbServiceInfo
    from .components.zeroconf import ZeroconfServiceInfo
    from .helpers.service_info.mqtt import MqttServiceInfo

_LOGGER = logging.getLogger(__name__)

SOURCE_BLUETOOTH = "bluetooth"
SOURCE_DHCP = "dhcp"
SOURCE_DISCOVERY = "discovery"
SOURCE_HASSIO = "hassio"
SOURCE_HOMEKIT = "homekit"
SOURCE_IMPORT = "import"
SOURCE_INTEGRATION_DISCOVERY = "integration_discovery"
SOURCE_MQTT = "mqtt"
SOURCE_SSDP = "ssdp"
SOURCE_USB = "usb"
SOURCE_USER = "user"
SOURCE_ZEROCONF = "zeroconf"

# If a user wants to hide a discovery from the UI they can "Ignore" it. The
# config_entries/ignore_flow websocket command creates a config entry with this
# source and while it exists normal discoveries with the same unique id are ignored.
SOURCE_IGNORE = "ignore"

# This is used when a user uses the "Stop Ignoring" button in the UI (the
# config_entries/ignore_flow websocket command). It's triggered after the
# "ignore" config entry has been removed and unloaded.
SOURCE_UNIGNORE = "unignore"

# This is used to signal that re-authentication is required by the user.
SOURCE_REAUTH = "reauth"

HANDLERS: Registry[str, type[ConfigFlow]] = Registry()

STORAGE_KEY = "core.config_entries"
STORAGE_VERSION = 1

# Deprecated since 0.73
PATH_CONFIG = ".config_entries.json"

SAVE_DELAY = 1

DISCOVERY_COOLDOWN = 1

_R = TypeVar("_R")


class ConfigEntryState(Enum):
    """Config entry state."""

    LOADED = "loaded", True
    """The config entry has been set up successfully"""
    SETUP_ERROR = "setup_error", True
    """There was an error while trying to set up this config entry"""
    MIGRATION_ERROR = "migration_error", False
    """There was an error while trying to migrate the config entry to a new version"""
    SETUP_RETRY = "setup_retry", True
    """The config entry was not ready to be set up yet, but might be later"""
    NOT_LOADED = "not_loaded", True
    """The config entry has not been loaded"""
    FAILED_UNLOAD = "failed_unload", False
    """An error occurred when trying to unload the entry"""
    SETUP_IN_PROGRESS = "setup_in_progress", False
    """The config entry is setting up."""

    _recoverable: bool

    def __new__(cls, value: str, recoverable: bool) -> Self:
        """Create new ConfigEntryState."""
        obj = object.__new__(cls)
        obj._value_ = value
        obj._recoverable = recoverable
        return obj

    @property
    def recoverable(self) -> bool:
        """Get if the state is recoverable.

        If the entry state is recoverable, unloads
        and reloads are allowed.
        """
        return self._recoverable


DEFAULT_DISCOVERY_UNIQUE_ID = "default_discovery_unique_id"
DISCOVERY_NOTIFICATION_ID = "config_entry_discovery"
DISCOVERY_SOURCES = {
    SOURCE_BLUETOOTH,
    SOURCE_DHCP,
    SOURCE_DISCOVERY,
    SOURCE_HOMEKIT,
    SOURCE_IMPORT,
    SOURCE_INTEGRATION_DISCOVERY,
    SOURCE_MQTT,
    SOURCE_SSDP,
    SOURCE_UNIGNORE,
    SOURCE_USB,
    SOURCE_ZEROCONF,
}

RECONFIGURE_NOTIFICATION_ID = "config_entry_reconfigure"

EVENT_FLOW_DISCOVERED = "config_entry_discovered"

SIGNAL_CONFIG_ENTRY_CHANGED = "config_entry_changed"


class ConfigEntryChange(StrEnum):
    """What was changed in a config entry."""

    ADDED = "added"
    REMOVED = "removed"
    UPDATED = "updated"


class ConfigEntryDisabler(StrEnum):
    """What disabled a config entry."""

    USER = "user"


# DISABLED_* is deprecated, to be removed in 2022.3
DISABLED_USER = ConfigEntryDisabler.USER.value

RELOAD_AFTER_UPDATE_DELAY = 30

# Deprecated: Connection classes
# These aren't used anymore since 2021.6.0
# Mainly here not to break custom integrations.
CONN_CLASS_CLOUD_PUSH = "cloud_push"
CONN_CLASS_CLOUD_POLL = "cloud_poll"
CONN_CLASS_LOCAL_PUSH = "local_push"
CONN_CLASS_LOCAL_POLL = "local_poll"
CONN_CLASS_ASSUMED = "assumed"
CONN_CLASS_UNKNOWN = "unknown"


class ConfigError(HomeAssistantError):
    """Error while configuring an account."""


class UnknownEntry(ConfigError):
    """Unknown entry specified."""


class OperationNotAllowed(ConfigError):
    """Raised when a config entry operation is not allowed."""


UpdateListenerType = Callable[[HomeAssistant, "ConfigEntry"], Coroutine[Any, Any, None]]


class ConfigEntry:
    """Hold a configuration entry."""

    __slots__ = (
        "entry_id",
        "version",
        "domain",
        "title",
        "data",
        "options",
        "unique_id",
        "supports_unload",
        "supports_remove_device",
        "pref_disable_new_entities",
        "pref_disable_polling",
        "source",
        "state",
        "disabled_by",
        "_setup_lock",
        "update_listeners",
        "reason",
        "_async_cancel_retry_setup",
        "_on_unload",
        "reload_lock",
        "_tasks",
        "_background_tasks",
        "_integration_for_domain",
        "_tries",
        "_setup_again_job",
    )

    def __init__(
        self,
        version: int,
        domain: str,
        title: str,
        data: Mapping[str, Any],
        source: str,
        pref_disable_new_entities: bool | None = None,
        pref_disable_polling: bool | None = None,
        options: Mapping[str, Any] | None = None,
        unique_id: str | None = None,
        entry_id: str | None = None,
        state: ConfigEntryState = ConfigEntryState.NOT_LOADED,
        disabled_by: ConfigEntryDisabler | None = None,
    ) -> None:
        """Initialize a config entry."""
        # Unique id of the config entry
        self.entry_id = entry_id or uuid_util.random_uuid_hex()

        # Version of the configuration.
        self.version = version

        # Domain the configuration belongs to
        self.domain = domain

        # Title of the configuration
        self.title = title

        # Config data
        self.data = MappingProxyType(data)

        # Entry options
        self.options = MappingProxyType(options or {})

        # Entry system options
        if pref_disable_new_entities is None:
            pref_disable_new_entities = False

        self.pref_disable_new_entities = pref_disable_new_entities

        if pref_disable_polling is None:
            pref_disable_polling = False

        self.pref_disable_polling = pref_disable_polling

        # Source of the configuration (user, discovery, cloud)
        self.source = source

        # State of the entry (LOADED, NOT_LOADED)
        self.state = state

        # Unique ID of this entry.
        self.unique_id = unique_id

        # Config entry is disabled
        if isinstance(disabled_by, str) and not isinstance(
            disabled_by, ConfigEntryDisabler
        ):
            report(  # type: ignore[unreachable]
                (
                    "uses str for config entry disabled_by. This is deprecated and will"
                    " stop working in Home Assistant 2022.3, it should be updated to"
                    " use ConfigEntryDisabler instead"
                ),
                error_if_core=False,
            )
            disabled_by = ConfigEntryDisabler(disabled_by)
        self.disabled_by = disabled_by

        # Supports unload
        self.supports_unload: bool | None = None

        # Supports remove device
        self.supports_remove_device: bool | None = None

        # Listeners to call on update
        self.update_listeners: list[UpdateListenerType] = []

        # Reason why config entry is in a failed state
        self.reason: str | None = None

        # Function to cancel a scheduled retry
        self._async_cancel_retry_setup: Callable[[], Any] | None = None

        # Hold list for actions to call on unload.
        self._on_unload: list[
            Callable[[], Coroutine[Any, Any, None] | None]
        ] | None = None

        # Reload lock to prevent conflicting reloads
        self.reload_lock = asyncio.Lock()

        self._tasks: set[asyncio.Future[Any]] = set()
        self._background_tasks: set[asyncio.Future[Any]] = set()

        self._integration_for_domain: loader.Integration | None = None
        self._tries = 0
        self._setup_again_job: HassJob | None = None

    async def async_setup(
        self,
        hass: HomeAssistant,
        *,
        integration: loader.Integration | None = None,
        tries: int | None = None,
    ) -> None:
        """Set up an entry."""
        current_entry.set(self)
        if self.source == SOURCE_IGNORE or self.disabled_by:
            return

        if integration is None:
            integration = await loader.async_get_integration(hass, self.domain)
            self._integration_for_domain = integration

        if tries is not None:
            self._tries = tries

        # Only store setup result as state if it was not forwarded.
        if self.domain == integration.domain:
            self._async_set_state(hass, ConfigEntryState.SETUP_IN_PROGRESS, None)

        if self.supports_unload is None:
            self.supports_unload = await support_entry_unload(hass, self.domain)
        if self.supports_remove_device is None:
            self.supports_remove_device = await support_remove_from_device(
                hass, self.domain
            )

        try:
            component = integration.get_component()
        except ImportError as err:
            _LOGGER.error(
                "Error importing integration %s to set up %s configuration entry: %s",
                integration.domain,
                self.domain,
                err,
            )
            if self.domain == integration.domain:
                self._async_set_state(
                    hass, ConfigEntryState.SETUP_ERROR, "Import error"
                )
            return

        if self.domain == integration.domain:
            try:
                integration.get_platform("config_flow")
            except ImportError as err:
                _LOGGER.error(
                    (
                        "Error importing platform config_flow from integration %s to"
                        " set up %s configuration entry: %s"
                    ),
                    integration.domain,
                    self.domain,
                    err,
                )
                self._async_set_state(
                    hass, ConfigEntryState.SETUP_ERROR, "Import error"
                )
                return

            # Perform migration
            if not await self.async_migrate(hass):
                self._async_set_state(hass, ConfigEntryState.MIGRATION_ERROR, None)
                return

        error_reason = None

        try:
            result = await component.async_setup_entry(hass, self)

            if not isinstance(result, bool):
                _LOGGER.error(  # type: ignore[unreachable]
                    "%s.async_setup_entry did not return boolean", integration.domain
                )
                result = False
        except ConfigEntryError as ex:
            error_reason = str(ex) or "Unknown fatal config entry error"
            _LOGGER.exception(
                "Error setting up entry %s for %s: %s",
                self.title,
                self.domain,
                error_reason,
            )
            await self._async_process_on_unload(hass)
            result = False
        except ConfigEntryAuthFailed as ex:
            message = str(ex)
            auth_base_message = "could not authenticate"
            error_reason = message or auth_base_message
            auth_message = (
                f"{auth_base_message}: {message}" if message else auth_base_message
            )
            _LOGGER.warning(
                "Config entry '%s' for %s integration %s",
                self.title,
                self.domain,
                auth_message,
            )
            await self._async_process_on_unload(hass)
            self.async_start_reauth(hass)
            result = False
        except ConfigEntryNotReady as ex:
            self._async_set_state(hass, ConfigEntryState.SETUP_RETRY, str(ex) or None)
            wait_time = 2 ** min(self._tries, 4) * 5 + (
                randint(RANDOM_MICROSECOND_MIN, RANDOM_MICROSECOND_MAX) / 1000000
            )
            self._tries += 1
            message = str(ex)
            ready_message = f"ready yet: {message}" if message else "ready yet"
            if self._tries == 1:
                _LOGGER.warning(
                    (
                        "Config entry '%s' for %s integration not %s; Retrying in"
                        " background"
                    ),
                    self.title,
                    self.domain,
                    ready_message,
                )
            else:
                _LOGGER.debug(
                    (
                        "Config entry '%s' for %s integration not %s; Retrying in %d"
                        " seconds"
                    ),
                    self.title,
                    self.domain,
                    ready_message,
                    wait_time,
                )

            if hass.state == CoreState.running:
                self._async_cancel_retry_setup = async_call_later(
                    hass, wait_time, self._async_get_setup_again_job(hass)
                )
            else:
                self._async_cancel_retry_setup = hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED,
                    functools.partial(self._async_setup_again, hass),
                )

            await self._async_process_on_unload(hass)
            return
        # pylint: disable-next=broad-except
        except (asyncio.CancelledError, SystemExit, Exception):
            _LOGGER.exception(
                "Error setting up entry %s for %s", self.title, integration.domain
            )
            result = False

        # Only store setup result as state if it was not forwarded.
        if self.domain != integration.domain:
            return

        if result:
            self._async_set_state(hass, ConfigEntryState.LOADED, None)
        else:
            self._async_set_state(hass, ConfigEntryState.SETUP_ERROR, error_reason)

    async def _async_setup_again(self, hass: HomeAssistant, *_: Any) -> None:
        """Run setup again."""
        # Check again when we fire in case shutdown
        # has started so we do not block shutdown
        if not hass.is_stopping:
            self._async_cancel_retry_setup = None
            await self.async_setup(hass)

    @callback
    def _async_get_setup_again_job(self, hass: HomeAssistant) -> HassJob:
        """Get a job that will call setup again."""
        if self._setup_again_job:
            return self._setup_again_job
        self._setup_again_job = HassJob(
            functools.partial(self._async_setup_again, hass)
        )
        return self._setup_again_job

    async def async_shutdown(self) -> None:
        """Call when Home Assistant is stopping."""
        self.async_cancel_retry_setup()

    @callback
    def async_cancel_retry_setup(self) -> None:
        """Cancel retry setup."""
        if self._async_cancel_retry_setup is not None:
            self._async_cancel_retry_setup()
            self._async_cancel_retry_setup = None

    async def async_unload(
        self, hass: HomeAssistant, *, integration: loader.Integration | None = None
    ) -> bool:
        """Unload an entry.

        Returns if unload is possible and was successful.
        """
        if self.source == SOURCE_IGNORE:
            self._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
            return True

        if self.state == ConfigEntryState.NOT_LOADED:
            return True

        if not integration and (integration := self._integration_for_domain) is None:
            try:
                integration = await loader.async_get_integration(hass, self.domain)
            except loader.IntegrationNotFound:
                # The integration was likely a custom_component
                # that was uninstalled, or an integration
                # that has been renamed without removing the config
                # entry.
                self._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
                return True

        component = integration.get_component()

        if integration.domain == self.domain:
            if not self.state.recoverable:
                return False

            if self.state is not ConfigEntryState.LOADED:
                self.async_cancel_retry_setup()
                self._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
                return True

        supports_unload = hasattr(component, "async_unload_entry")

        if not supports_unload:
            if integration.domain == self.domain:
                self._async_set_state(
                    hass, ConfigEntryState.FAILED_UNLOAD, "Unload not supported"
                )
            return False

        try:
            result = await component.async_unload_entry(hass, self)

            assert isinstance(result, bool)

            # Only adjust state if we unloaded the component
            if result and integration.domain == self.domain:
                self._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)

            await self._async_process_on_unload(hass)

            return result
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error unloading entry %s for %s", self.title, integration.domain
            )
            if integration.domain == self.domain:
                self._async_set_state(
                    hass, ConfigEntryState.FAILED_UNLOAD, str(ex) or "Unknown error"
                )
            return False

    async def async_remove(self, hass: HomeAssistant) -> None:
        """Invoke remove callback on component."""
        if self.source == SOURCE_IGNORE:
            return

        if not (integration := self._integration_for_domain):
            try:
                integration = await loader.async_get_integration(hass, self.domain)
            except loader.IntegrationNotFound:
                # The integration was likely a custom_component
                # that was uninstalled, or an integration
                # that has been renamed without removing the config
                # entry.
                return

        component = integration.get_component()
        if not hasattr(component, "async_remove_entry"):
            return
        try:
            await component.async_remove_entry(hass, self)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error calling entry remove callback %s for %s",
                self.title,
                integration.domain,
            )

    @callback
    def _async_set_state(
        self, hass: HomeAssistant, state: ConfigEntryState, reason: str | None
    ) -> None:
        """Set the state of the config entry."""
        if state not in {
            ConfigEntryState.SETUP_RETRY,
            ConfigEntryState.SETUP_IN_PROGRESS,
        }:
            self._tries = 0
        self.state = state
        self.reason = reason
        async_dispatcher_send(
            hass, SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntryChange.UPDATED, self
        )

    async def async_migrate(self, hass: HomeAssistant) -> bool:
        """Migrate an entry.

        Returns True if config entry is up-to-date or has been migrated.
        """
        if (handler := HANDLERS.get(self.domain)) is None:
            _LOGGER.error(
                "Flow handler not found for entry %s for %s", self.title, self.domain
            )
            return False
        # Handler may be a partial
        # Keep for backwards compatibility
        # https://github.com/home-assistant/core/pull/67087#discussion_r812559950
        while isinstance(handler, functools.partial):
            handler = handler.func  # type: ignore[unreachable]

        if self.version == handler.VERSION:
            return True

        if not (integration := self._integration_for_domain):
            integration = await loader.async_get_integration(hass, self.domain)
        component = integration.get_component()
        supports_migrate = hasattr(component, "async_migrate_entry")
        if not supports_migrate:
            _LOGGER.error(
                "Migration handler not found for entry %s for %s",
                self.title,
                self.domain,
            )
            return False

        try:
            result = await component.async_migrate_entry(hass, self)
            if not isinstance(result, bool):
                _LOGGER.error(  # type: ignore[unreachable]
                    "%s.async_migrate_entry did not return boolean", self.domain
                )
                return False
            if result:
                # pylint: disable-next=protected-access
                hass.config_entries._async_schedule_save()
            return result
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error migrating entry %s for %s", self.title, self.domain
            )
            return False

    def add_update_listener(self, listener: UpdateListenerType) -> CALLBACK_TYPE:
        """Listen for when entry is updated.

        Returns function to unlisten.
        """
        self.update_listeners.append(listener)
        return lambda: self.update_listeners.remove(listener)

    def as_dict(self) -> dict[str, Any]:
        """Return dictionary version of this entry."""
        return {
            "entry_id": self.entry_id,
            "version": self.version,
            "domain": self.domain,
            "title": self.title,
            "data": dict(self.data),
            "options": dict(self.options),
            "pref_disable_new_entities": self.pref_disable_new_entities,
            "pref_disable_polling": self.pref_disable_polling,
            "source": self.source,
            "unique_id": self.unique_id,
            "disabled_by": self.disabled_by,
        }

    @callback
    def async_on_unload(
        self, func: Callable[[], Coroutine[Any, Any, None] | None]
    ) -> None:
        """Add a function to call when config entry is unloaded."""
        if self._on_unload is None:
            self._on_unload = []
        self._on_unload.append(func)

    async def _async_process_on_unload(self, hass: HomeAssistant) -> None:
        """Process the on_unload callbacks and wait for pending tasks."""
        if self._on_unload is not None:
            while self._on_unload:
                if job := self._on_unload.pop()():
                    self.async_create_task(hass, job)

        if not self._tasks and not self._background_tasks:
            return

        cancel_message = f"Config entry {self.title} with {self.domain} unloading"
        for task in self._background_tasks:
            task.cancel(cancel_message)

        _, pending = await asyncio.wait(
            [*self._tasks, *self._background_tasks], timeout=10
        )

        for task in pending:
            _LOGGER.warning(
                "Unloading %s (%s) config entry. Task %s did not complete in time",
                self.title,
                self.domain,
                task,
            )

    @callback
    def async_start_reauth(
        self,
        hass: HomeAssistant,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Start a reauth flow."""
        if any(self.async_get_active_flows(hass, {SOURCE_REAUTH})):
            # Reauth flow already in progress for this entry
            return

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                self.domain,
                context={
                    "source": SOURCE_REAUTH,
                    "entry_id": self.entry_id,
                    "title_placeholders": {"name": self.title},
                    "unique_id": self.unique_id,
                }
                | (context or {}),
                data=self.data | (data or {}),
            ),
            f"config entry reauth {self.title} {self.domain} {self.entry_id}",
        )

    @callback
    def async_get_active_flows(
        self, hass: HomeAssistant, sources: set[str]
    ) -> Generator[FlowResult, None, None]:
        """Get any active flows of certain sources for this entry."""
        return (
            flow
            for flow in hass.config_entries.flow.async_progress_by_handler(
                self.domain, match_context={"entry_id": self.entry_id}
            )
            if flow["context"].get("source") in sources
        )

    @callback
    def async_create_task(
        self,
        hass: HomeAssistant,
        target: Coroutine[Any, Any, _R],
        name: str | None = None,
    ) -> asyncio.Task[_R]:
        """Create a task from within the event loop.

        This method must be run in the event loop.

        target: target to call.
        """
        task = hass.async_create_task(
            target, f"{name} {self.title} {self.domain} {self.entry_id}"
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.remove)

        return task

    @callback
    def async_create_background_task(
        self, hass: HomeAssistant, target: Coroutine[Any, Any, _R], name: str
    ) -> asyncio.Task[_R]:
        """Create a background task tied to the config entry lifecycle.

        Background tasks are automatically canceled when config entry is unloaded.

        target: target to call.
        """
        task = hass.async_create_background_task(target, name)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.remove)
        return task


current_entry: ContextVar[ConfigEntry | None] = ContextVar(
    "current_entry", default=None
)


class ConfigEntriesFlowManager(data_entry_flow.FlowManager):
    """Manage all the config entry flows that are in progress."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entries: ConfigEntries,
        hass_config: ConfigType,
    ) -> None:
        """Initialize the config entry flow manager."""
        super().__init__(hass)
        self.config_entries = config_entries
        self._hass_config = hass_config
        self._pending_import_flows: dict[str, dict[str, asyncio.Future[None]]] = {}
        self._initialize_tasks: dict[str, list[asyncio.Task]] = {}
        self._discovery_debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=DISCOVERY_COOLDOWN,
            immediate=True,
            function=self._async_discovery,
        )

    async def async_wait_import_flow_initialized(self, handler: str) -> None:
        """Wait till all import flows in progress are initialized."""
        if not (current := self._pending_import_flows.get(handler)):
            return

        await asyncio.wait(current.values())

    @callback
    def _async_has_other_discovery_flows(self, flow_id: str) -> bool:
        """Check if there are any other discovery flows in progress."""
        return any(
            flow.context["source"] in DISCOVERY_SOURCES and flow.flow_id != flow_id
            for flow in self._progress.values()
        )

    async def async_init(
        self, handler: str, *, context: dict[str, Any] | None = None, data: Any = None
    ) -> FlowResult:
        """Start a configuration flow."""
        if not context or "source" not in context:
            raise KeyError("Context not set or doesn't have a source set")

        flow_id = uuid_util.random_uuid_hex()
        if context["source"] == SOURCE_IMPORT:
            init_done: asyncio.Future[None] = asyncio.Future()
            self._pending_import_flows.setdefault(handler, {})[flow_id] = init_done

        task = asyncio.create_task(
            self._async_init(flow_id, handler, context, data),
            name=f"config entry flow {handler} {flow_id}",
        )
        self._initialize_tasks.setdefault(handler, []).append(task)

        try:
            flow, result = await task
        finally:
            self._initialize_tasks[handler].remove(task)
            self._pending_import_flows.get(handler, {}).pop(flow_id, None)

        if result["type"] != data_entry_flow.FlowResultType.ABORT:
            await self.async_post_init(flow, result)

        return result

    async def _async_init(
        self,
        flow_id: str,
        handler: str,
        context: dict,
        data: Any,
    ) -> tuple[data_entry_flow.FlowHandler, FlowResult]:
        """Run the init in a task to allow it to be canceled at shutdown."""
        flow = await self.async_create_flow(handler, context=context, data=data)
        if not flow:
            raise data_entry_flow.UnknownFlow("Flow was not created")
        flow.hass = self.hass
        flow.handler = handler
        flow.flow_id = flow_id
        flow.context = context
        flow.init_data = data
        self._async_add_flow_progress(flow)
        try:
            result = await self._async_handle_step(flow, flow.init_step, data)
        finally:
            init_done = self._pending_import_flows.get(handler, {}).get(flow_id)
            if init_done and not init_done.done():
                init_done.set_result(None)
        return flow, result

    async def async_shutdown(self) -> None:
        """Cancel any initializing flows."""
        for task_list in self._initialize_tasks.values():
            for task in task_list:
                task.cancel(
                    "Config entry initialize canceled: Home Assistant is shutting down"
                )
        await self._discovery_debouncer.async_shutdown()

    async def async_finish_flow(
        self, flow: data_entry_flow.FlowHandler, result: data_entry_flow.FlowResult
    ) -> data_entry_flow.FlowResult:
        """Finish a config flow and add an entry."""
        flow = cast(ConfigFlow, flow)

        # Mark the step as done.
        # We do this to avoid a circular dependency where async_finish_flow sets up a
        # new entry, which needs the integration to be set up, which is waiting for
        # init to be done.
        init_done = self._pending_import_flows.get(flow.handler, {}).get(flow.flow_id)
        if init_done and not init_done.done():
            init_done.set_result(None)

        # Remove notification if no other discovery config entries in progress
        if not self._async_has_other_discovery_flows(flow.flow_id):
            persistent_notification.async_dismiss(self.hass, DISCOVERY_NOTIFICATION_ID)

        if result["type"] != data_entry_flow.FlowResultType.CREATE_ENTRY:
            return result

        # Check if config entry exists with unique ID. Unload it.
        existing_entry = None

        # Abort all flows in progress with same unique ID
        # or the default discovery ID
        for progress_flow in self.async_progress_by_handler(flow.handler):
            progress_unique_id = progress_flow["context"].get("unique_id")
            if progress_flow["flow_id"] != flow.flow_id and (
                (flow.unique_id and progress_unique_id == flow.unique_id)
                or progress_unique_id == DEFAULT_DISCOVERY_UNIQUE_ID
            ):
                self.async_abort(progress_flow["flow_id"])

        if flow.unique_id is not None:
            # Reset unique ID when the default discovery ID has been used
            if flow.unique_id == DEFAULT_DISCOVERY_UNIQUE_ID:
                await flow.async_set_unique_id(None)

            # Find existing entry.
            for check_entry in self.config_entries.async_entries(result["handler"]):
                if check_entry.unique_id == flow.unique_id:
                    existing_entry = check_entry
                    break

        # Unload the entry before setting up the new one.
        # We will remove it only after the other one is set up,
        # so that device customizations are not getting lost.
        if existing_entry is not None and existing_entry.state.recoverable:
            await self.config_entries.async_unload(existing_entry.entry_id)

        entry = ConfigEntry(
            version=result["version"],
            domain=result["handler"],
            title=result["title"],
            data=result["data"],
            options=result["options"],
            source=flow.context["source"],
            unique_id=flow.unique_id,
        )

        await self.config_entries.async_add(entry)

        if existing_entry is not None:
            await self.config_entries.async_remove(existing_entry.entry_id)

        result["result"] = entry
        return result

    async def async_create_flow(
        self, handler_key: str, *, context: dict | None = None, data: Any = None
    ) -> ConfigFlow:
        """Create a flow for specified handler.

        Handler key is the domain of the component that we want to set up.
        """
        handler = await _async_get_flow_handler(
            self.hass, handler_key, self._hass_config
        )
        if not context or "source" not in context:
            raise KeyError("Context not set or doesn't have a source set")

        flow = handler()
        flow.init_step = context["source"]
        return flow

    async def async_post_init(
        self, flow: data_entry_flow.FlowHandler, result: data_entry_flow.FlowResult
    ) -> None:
        """After a flow is initialised trigger new flow notifications."""
        source = flow.context["source"]

        # Create notification.
        if source in DISCOVERY_SOURCES:
            await self._discovery_debouncer.async_call()
        elif source == SOURCE_REAUTH:
            persistent_notification.async_create(
                self.hass,
                title="Integration requires reconfiguration",
                message=(
                    "At least one of your integrations requires reconfiguration to "
                    "continue functioning. [Check it out](/config/integrations)."
                ),
                notification_id=RECONFIGURE_NOTIFICATION_ID,
            )

    @callback
    def _async_discovery(self) -> None:
        """Handle discovery."""
        self.hass.bus.async_fire(EVENT_FLOW_DISCOVERED)
        persistent_notification.async_create(
            self.hass,
            title="New devices discovered",
            message=(
                "We have discovered new devices on your network. "
                "[Check it out](/config/integrations)."
            ),
            notification_id=DISCOVERY_NOTIFICATION_ID,
        )


class ConfigEntries:
    """Manage the configuration entries.

    An instance of this object is available via `hass.config_entries`.
    """

    def __init__(self, hass: HomeAssistant, hass_config: ConfigType) -> None:
        """Initialize the entry manager."""
        self.hass = hass
        self.flow = ConfigEntriesFlowManager(hass, self, hass_config)
        self.options = OptionsFlowManager(hass)
        self._hass_config = hass_config
        self._entries: dict[str, ConfigEntry] = {}
        self._domain_index: dict[str, list[str]] = {}
        self._store = storage.Store[dict[str, list[dict[str, Any]]]](
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        EntityRegistryDisabledHandler(hass).async_setup()

    @callback
    def async_domains(
        self, include_ignore: bool = False, include_disabled: bool = False
    ) -> list[str]:
        """Return domains for which we have entries."""
        return list(
            {
                entry.domain: None
                for entry in self._entries.values()
                if (include_ignore or entry.source != SOURCE_IGNORE)
                and (include_disabled or not entry.disabled_by)
            }
        )

    @callback
    def async_get_entry(self, entry_id: str) -> ConfigEntry | None:
        """Return entry with matching entry_id."""
        return self._entries.get(entry_id)

    @callback
    def async_entries(self, domain: str | None = None) -> list[ConfigEntry]:
        """Return all entries or entries for a specific domain."""
        if domain is None:
            return list(self._entries.values())
        return [
            self._entries[entry_id] for entry_id in self._domain_index.get(domain, [])
        ]

    async def async_add(self, entry: ConfigEntry) -> None:
        """Add and setup an entry."""
        if entry.entry_id in self._entries:
            raise HomeAssistantError(
                f"An entry with the id {entry.entry_id} already exists."
            )
        self._entries[entry.entry_id] = entry
        self._domain_index.setdefault(entry.domain, []).append(entry.entry_id)
        self._async_dispatch(ConfigEntryChange.ADDED, entry)
        await self.async_setup(entry.entry_id)
        self._async_schedule_save()

    async def async_remove(self, entry_id: str) -> dict[str, Any]:
        """Remove an entry."""
        if (entry := self.async_get_entry(entry_id)) is None:
            raise UnknownEntry

        if not entry.state.recoverable:
            unload_success = entry.state is not ConfigEntryState.FAILED_UNLOAD
        else:
            unload_success = await self.async_unload(entry_id)

        await entry.async_remove(self.hass)

        del self._entries[entry.entry_id]
        self._domain_index[entry.domain].remove(entry.entry_id)
        if not self._domain_index[entry.domain]:
            del self._domain_index[entry.domain]
        self._async_schedule_save()

        dev_reg = device_registry.async_get(self.hass)
        ent_reg = entity_registry.async_get(self.hass)

        dev_reg.async_clear_config_entry(entry_id)
        ent_reg.async_clear_config_entry(entry_id)

        # If the configuration entry is removed during reauth, it should
        # abort any reauth flow that is active for the removed entry.
        for progress_flow in self.hass.config_entries.flow.async_progress_by_handler(
            entry.domain, match_context={"entry_id": entry_id, "source": SOURCE_REAUTH}
        ):
            if "flow_id" in progress_flow:
                self.hass.config_entries.flow.async_abort(progress_flow["flow_id"])

        # After we have fully removed an "ignore" config entry we can try and rediscover
        # it so that a user is able to immediately start configuring it. We do this by
        # starting a new flow with the 'unignore' step. If the integration doesn't
        # implement async_step_unignore then this will be a no-op.
        if entry.source == SOURCE_IGNORE:
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    entry.domain,
                    context={"source": SOURCE_UNIGNORE},
                    data={"unique_id": entry.unique_id},
                ),
                f"config entry unignore {entry.title} {entry.domain} {entry.unique_id}",
            )

        self._async_dispatch(ConfigEntryChange.REMOVED, entry)
        return {"require_restart": not unload_success}

    async def _async_shutdown(self, event: Event) -> None:
        """Call when Home Assistant is stopping."""
        await asyncio.gather(
            *(
                asyncio.create_task(
                    entry.async_shutdown(),
                    name=f"config entry shutdown {entry.title} {entry.domain} {entry.entry_id}",
                )
                for entry in self._entries.values()
            )
        )
        await self.flow.async_shutdown()

    async def async_initialize(self) -> None:
        """Initialize config entry config."""
        # Migrating for config entries stored before 0.73
        config = await storage.async_migrator(
            self.hass,
            self.hass.config.path(PATH_CONFIG),
            self._store,
            old_conf_migrate_func=_old_conf_migrator,
        )

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_shutdown)

        if config is None:
            self._entries = {}
            self._domain_index = {}
            return

        entries = {}
        domain_index: dict[str, list[str]] = {}

        for entry in config["entries"]:
            pref_disable_new_entities = entry.get("pref_disable_new_entities")

            # Between 0.98 and 2021.6 we stored 'disable_new_entities' in a
            # system options dictionary.
            if pref_disable_new_entities is None and "system_options" in entry:
                pref_disable_new_entities = entry.get("system_options", {}).get(
                    "disable_new_entities"
                )

            domain = entry["domain"]
            entry_id = entry["entry_id"]

            entries[entry_id] = ConfigEntry(
                version=entry["version"],
                domain=domain,
                entry_id=entry_id,
                data=entry["data"],
                source=entry["source"],
                title=entry["title"],
                # New in 0.89
                options=entry.get("options"),
                # New in 0.104
                unique_id=entry.get("unique_id"),
                # New in 2021.3
                disabled_by=ConfigEntryDisabler(entry["disabled_by"])
                if entry.get("disabled_by")
                else None,
                # New in 2021.6
                pref_disable_new_entities=pref_disable_new_entities,
                pref_disable_polling=entry.get("pref_disable_polling"),
            )
            domain_index.setdefault(domain, []).append(entry_id)

        self._domain_index = domain_index
        self._entries = entries

    async def async_setup(self, entry_id: str) -> bool:
        """Set up a config entry.

        Return True if entry has been successfully loaded.
        """
        if (entry := self.async_get_entry(entry_id)) is None:
            raise UnknownEntry

        if entry.state is not ConfigEntryState.NOT_LOADED:
            raise OperationNotAllowed(
                f"The config entry {entry.title} ({entry.domain}) with entry_id"
                f" {entry.entry_id} cannot be setup because is already loaded in the"
                f" {entry.state} state"
            )

        # Setup Component if not set up yet
        if entry.domain in self.hass.config.components:
            await entry.async_setup(self.hass)
        else:
            # Setting up the component will set up all its config entries
            result = await async_setup_component(
                self.hass, entry.domain, self._hass_config
            )

            if not result:
                return result

        return (
            entry.state is ConfigEntryState.LOADED  # type: ignore[comparison-overlap]
        )

    async def async_unload(self, entry_id: str) -> bool:
        """Unload a config entry."""
        if (entry := self.async_get_entry(entry_id)) is None:
            raise UnknownEntry

        if not entry.state.recoverable:
            raise OperationNotAllowed(
                f"The config entry {entry.title} ({entry.domain}) with entry_id"
                f" {entry.entry_id} cannot be unloaded because it is not in a"
                f" recoverable state ({entry.state})"
            )

        return await entry.async_unload(self.hass)

    async def async_reload(self, entry_id: str) -> bool:
        """Reload an entry.

        If an entry was not loaded, will just load.
        """
        if (entry := self.async_get_entry(entry_id)) is None:
            raise UnknownEntry

        async with entry.reload_lock:
            unload_result = await self.async_unload(entry_id)

            if not unload_result or entry.disabled_by:
                return unload_result

            return await self.async_setup(entry_id)

    async def async_set_disabled_by(
        self, entry_id: str, disabled_by: ConfigEntryDisabler | None
    ) -> bool:
        """Disable an entry.

        If disabled_by is changed, the config entry will be reloaded.
        """
        if (entry := self.async_get_entry(entry_id)) is None:
            raise UnknownEntry

        if isinstance(disabled_by, str) and not isinstance(
            disabled_by, ConfigEntryDisabler
        ):
            report(  # type: ignore[unreachable]
                (
                    "uses str for config entry disabled_by. This is deprecated and will"
                    " stop working in Home Assistant 2022.3, it should be updated to"
                    " use ConfigEntryDisabler instead"
                ),
                error_if_core=False,
            )
            disabled_by = ConfigEntryDisabler(disabled_by)

        if entry.disabled_by is disabled_by:
            return True

        entry.disabled_by = disabled_by
        self._async_schedule_save()

        dev_reg = device_registry.async_get(self.hass)
        ent_reg = entity_registry.async_get(self.hass)

        if not entry.disabled_by:
            # The config entry will no longer be disabled, enable devices and entities
            device_registry.async_config_entry_disabled_by_changed(dev_reg, entry)
            entity_registry.async_config_entry_disabled_by_changed(ent_reg, entry)

        # Load or unload the config entry
        reload_result = await self.async_reload(entry_id)

        if entry.disabled_by:
            # The config entry has been disabled, disable devices and entities
            device_registry.async_config_entry_disabled_by_changed(dev_reg, entry)
            entity_registry.async_config_entry_disabled_by_changed(ent_reg, entry)

        return reload_result

    @callback
    def async_update_entry(
        self,
        entry: ConfigEntry,
        *,
        unique_id: str | None | UndefinedType = UNDEFINED,
        title: str | UndefinedType = UNDEFINED,
        data: Mapping[str, Any] | UndefinedType = UNDEFINED,
        options: Mapping[str, Any] | UndefinedType = UNDEFINED,
        pref_disable_new_entities: bool | UndefinedType = UNDEFINED,
        pref_disable_polling: bool | UndefinedType = UNDEFINED,
    ) -> bool:
        """Update a config entry.

        If the entry was changed, the update_listeners are
        fired and this function returns True

        If the entry was not changed, the update_listeners are
        not fired and this function returns False
        """
        changed = False

        for attr, value in (
            ("unique_id", unique_id),
            ("title", title),
            ("pref_disable_new_entities", pref_disable_new_entities),
            ("pref_disable_polling", pref_disable_polling),
        ):
            if value == UNDEFINED or getattr(entry, attr) == value:
                continue

            setattr(entry, attr, value)
            changed = True

        if data is not UNDEFINED and entry.data != data:
            changed = True
            entry.data = MappingProxyType(data)

        if options is not UNDEFINED and entry.options != options:
            changed = True
            entry.options = MappingProxyType(options)

        if not changed:
            return False

        for listener in entry.update_listeners:
            self.hass.async_create_task(
                listener(self.hass, entry),
                f"config entry update listener {entry.title} {entry.domain} {entry.domain}",
            )

        self._async_schedule_save()
        self._async_dispatch(ConfigEntryChange.UPDATED, entry)
        return True

    @callback
    def _async_dispatch(
        self, change_type: ConfigEntryChange, entry: ConfigEntry
    ) -> None:
        """Dispatch a config entry change."""
        async_dispatcher_send(
            self.hass, SIGNAL_CONFIG_ENTRY_CHANGED, change_type, entry
        )

    async def async_forward_entry_setups(
        self, entry: ConfigEntry, platforms: Iterable[Platform | str]
    ) -> None:
        """Forward the setup of an entry to platforms."""
        await asyncio.gather(
            *(
                asyncio.create_task(
                    self.async_forward_entry_setup(entry, platform),
                    name=f"config entry forward setup {entry.title} {entry.domain} {entry.entry_id} {platform}",
                )
                for platform in platforms
            )
        )

    async def async_forward_entry_setup(
        self, entry: ConfigEntry, domain: Platform | str
    ) -> bool:
        """Forward the setup of an entry to a different component.

        By default an entry is setup with the component it belongs to. If that
        component also has related platforms, the component will have to
        forward the entry to be setup by that component.
        """
        # Setup Component if not set up yet
        if domain not in self.hass.config.components:
            result = await async_setup_component(self.hass, domain, self._hass_config)

            if not result:
                return False

        integration = await loader.async_get_integration(self.hass, domain)

        await entry.async_setup(self.hass, integration=integration)
        return True

    async def async_unload_platforms(
        self, entry: ConfigEntry, platforms: Iterable[Platform | str]
    ) -> bool:
        """Forward the unloading of an entry to platforms."""
        return all(
            await asyncio.gather(
                *(
                    asyncio.create_task(
                        self.async_forward_entry_unload(entry, platform),
                        name=f"config entry forward unload {entry.title} {entry.domain} {entry.entry_id} {platform}",
                    )
                    for platform in platforms
                )
            )
        )

    async def async_forward_entry_unload(
        self, entry: ConfigEntry, domain: Platform | str
    ) -> bool:
        """Forward the unloading of an entry to a different component."""
        # It was never loaded.
        if domain not in self.hass.config.components:
            return True

        integration = await loader.async_get_integration(self.hass, domain)

        return await entry.async_unload(self.hass, integration=integration)

    @callback
    def _async_schedule_save(self) -> None:
        """Save the entity registry to a file."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, Any]]]:
        """Return data to save."""
        return {"entries": [entry.as_dict() for entry in self._entries.values()]}

    async def async_wait_component(self, entry: ConfigEntry) -> bool:
        """Wait for an entry's component to load and return if the entry is loaded.

        This is primarily intended for existing config entries which are loaded at
        startup, awaiting this function will block until the component and all its
        config entries are loaded.
        Config entries which are created after Home Assistant is started can't be waited
        for, the function will just return if the config entry is loaded or not.
        """
        if setup_event := self.hass.data.get(DATA_SETUP_DONE, {}).get(entry.domain):
            await setup_event.wait()
        # The component was not loaded.
        if entry.domain not in self.hass.config.components:
            return False
        return entry.state == ConfigEntryState.LOADED


async def _old_conf_migrator(old_config: dict[str, Any]) -> dict[str, Any]:
    """Migrate the pre-0.73 config format to the latest version."""
    return {"entries": old_config}


@callback
def _async_abort_entries_match(
    other_entries: list[ConfigEntry], match_dict: dict[str, Any] | None = None
) -> None:
    """Abort if current entries match all data.

    Requires `already_configured` in strings.json in user visible flows.
    """
    if match_dict is None:
        match_dict = {}  # Match any entry
    for entry in other_entries:
        options_items = entry.options.items()
        data_items = entry.data.items()
        for kv in match_dict.items():
            if kv not in options_items and kv not in data_items:
                break
        else:
            raise data_entry_flow.AbortFlow("already_configured")


class ConfigFlow(data_entry_flow.FlowHandler):
    """Base class for config flows with some helpers."""

    def __init_subclass__(cls, *, domain: str | None = None, **kwargs: Any) -> None:
        """Initialize a subclass, register if possible."""
        super().__init_subclass__(**kwargs)
        if domain is not None:
            HANDLERS.register(domain)(cls)

    @property
    def unique_id(self) -> str | None:
        """Return unique ID if available."""
        if not self.context:
            return None

        return cast(str | None, self.context.get("unique_id"))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        raise data_entry_flow.UnknownHandler

    @classmethod
    @callback
    def async_supports_options_flow(cls, config_entry: ConfigEntry) -> bool:
        """Return options flow support for this handler."""
        return cls.async_get_options_flow is not ConfigFlow.async_get_options_flow

    @callback
    def _async_abort_entries_match(
        self, match_dict: dict[str, Any] | None = None
    ) -> None:
        """Abort if current entries match all data.

        Requires `already_configured` in strings.json in user visible flows.
        """
        _async_abort_entries_match(
            self._async_current_entries(include_ignore=False), match_dict
        )

    @callback
    def _abort_if_unique_id_configured(
        self,
        updates: dict[str, Any] | None = None,
        reload_on_update: bool = True,
        *,
        error: str = "already_configured",
    ) -> None:
        """Abort if the unique ID is already configured.

        Requires strings.json entry corresponding to the `error` parameter
        in user visible flows.
        """
        if self.unique_id is None:
            return

        for entry in self._async_current_entries(include_ignore=True):
            if entry.unique_id != self.unique_id:
                continue
            should_reload = False
            if (
                updates is not None
                and self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, **updates}
                )
                and reload_on_update
                and entry.state
                in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY)
            ):
                # Existing config entry present, and the
                # entry data just changed
                should_reload = True
            elif (
                self.source in DISCOVERY_SOURCES
                and entry.state is ConfigEntryState.SETUP_RETRY
            ):
                # Existing config entry present in retry state, and we
                # just discovered the unique id so we know its online
                should_reload = True
            # Allow ignored entries to be configured on manual user step
            if entry.source == SOURCE_IGNORE and self.source == SOURCE_USER:
                continue
            if should_reload:
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id),
                    f"config entry reload {entry.title} {entry.domain} {entry.entry_id}",
                )
            raise data_entry_flow.AbortFlow(error)

    async def async_set_unique_id(
        self, unique_id: str | None = None, *, raise_on_progress: bool = True
    ) -> ConfigEntry | None:
        """Set a unique ID for the config flow.

        Returns optionally existing config entry with same ID.
        """
        if unique_id is None:
            self.context["unique_id"] = None
            return None

        if raise_on_progress:
            if self._async_in_progress(
                include_uninitialized=True, match_context={"unique_id": unique_id}
            ):
                raise data_entry_flow.AbortFlow("already_in_progress")

        self.context["unique_id"] = unique_id

        # Abort discoveries done using the default discovery unique id
        if unique_id != DEFAULT_DISCOVERY_UNIQUE_ID:
            for progress in self._async_in_progress(
                include_uninitialized=True,
                match_context={"unique_id": DEFAULT_DISCOVERY_UNIQUE_ID},
            ):
                self.hass.config_entries.flow.async_abort(progress["flow_id"])

        for entry in self._async_current_entries(include_ignore=True):
            if entry.unique_id == unique_id:
                return entry

        return None

    @callback
    def _set_confirm_only(
        self,
    ) -> None:
        """Mark the config flow as only needing user confirmation to finish flow."""
        self.context["confirm_only"] = True

    @callback
    def _async_current_entries(
        self, include_ignore: bool | None = None
    ) -> list[ConfigEntry]:
        """Return current entries.

        If the flow is user initiated, filter out ignored entries,
        unless include_ignore is True.
        """
        config_entries = self.hass.config_entries.async_entries(self.handler)

        if (
            include_ignore is True
            or include_ignore is None
            and self.source != SOURCE_USER
        ):
            return config_entries

        return [entry for entry in config_entries if entry.source != SOURCE_IGNORE]

    @callback
    def _async_current_ids(self, include_ignore: bool = True) -> set[str | None]:
        """Return current unique IDs."""
        return {
            entry.unique_id
            for entry in self.hass.config_entries.async_entries(self.handler)
            if include_ignore or entry.source != SOURCE_IGNORE
        }

    @callback
    def _async_in_progress(
        self,
        include_uninitialized: bool = False,
        match_context: dict[str, Any] | None = None,
    ) -> list[data_entry_flow.FlowResult]:
        """Return other in progress flows for current domain."""
        return [
            flw
            for flw in self.hass.config_entries.flow.async_progress_by_handler(
                self.handler,
                include_uninitialized=include_uninitialized,
                match_context=match_context,
            )
            if flw["flow_id"] != self.flow_id
        ]

    async def async_step_ignore(
        self, user_input: dict[str, Any]
    ) -> data_entry_flow.FlowResult:
        """Ignore this config flow."""
        await self.async_set_unique_id(user_input["unique_id"], raise_on_progress=False)
        return self.async_create_entry(title=user_input["title"], data={})

    async def async_step_unignore(
        self, user_input: dict[str, Any]
    ) -> data_entry_flow.FlowResult:
        """Rediscover a config entry by it's unique_id."""
        return self.async_abort(reason="not_implemented")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initiated by the user."""
        return self.async_abort(reason="not_implemented")

    async def _async_handle_discovery_without_unique_id(self) -> None:
        """Mark this flow discovered, without a unique identifier.

        If a flow initiated by discovery, doesn't have a unique ID, this can
        be used alternatively. It will ensure only 1 flow is started and only
        when the handler has no existing config entries.

        It ensures that the discovery can be ignored by the user.

        Requires `already_configured` and `already_in_progress` in strings.json
        in user visible flows.
        """
        if self.unique_id is not None:
            return

        # Abort if the handler has config entries already
        if self._async_current_entries():
            raise data_entry_flow.AbortFlow("already_configured")

        # Use an special unique id to differentiate
        await self.async_set_unique_id(DEFAULT_DISCOVERY_UNIQUE_ID)
        self._abort_if_unique_id_configured()

        # Abort if any other flow for this handler is already in progress
        if self._async_in_progress(include_uninitialized=True):
            raise data_entry_flow.AbortFlow("already_in_progress")

    async def _async_step_discovery_without_unique_id(
        self,
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by discovery."""
        await self._async_handle_discovery_without_unique_id()
        return await self.async_step_user()

    async def async_step_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by discovery."""
        return await self._async_step_discovery_without_unique_id()

    @callback
    def async_abort(
        self,
        *,
        reason: str,
        description_placeholders: Mapping[str, str] | None = None,
    ) -> data_entry_flow.FlowResult:
        """Abort the config flow."""
        # Remove reauth notification if no reauth flows are in progress
        if self.source == SOURCE_REAUTH and not any(
            ent["flow_id"] != self.flow_id
            for ent in self.hass.config_entries.flow.async_progress_by_handler(
                self.handler, match_context={"source": SOURCE_REAUTH}
            )
        ):
            persistent_notification.async_dismiss(
                self.hass, RECONFIGURE_NOTIFICATION_ID
            )

        return super().async_abort(
            reason=reason, description_placeholders=description_placeholders
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by Bluetooth discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by DHCP discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by HASS IO discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by integration specific discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by Homekit discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by MQTT discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by SSDP discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_usb(
        self, discovery_info: UsbServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by USB discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by Zeroconf discovery."""
        return await self._async_step_discovery_without_unique_id()

    @callback
    def async_create_entry(  # type: ignore[override]
        self,
        *,
        title: str,
        data: Mapping[str, Any],
        description: str | None = None,
        description_placeholders: Mapping[str, str] | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> data_entry_flow.FlowResult:
        """Finish config flow and create a config entry."""
        result = super().async_create_entry(
            title=title,
            data=data,
            description=description,
            description_placeholders=description_placeholders,
        )

        result["options"] = options or {}

        return result


class OptionsFlowManager(data_entry_flow.FlowManager):
    """Flow to set options for a configuration entry."""

    def _async_get_config_entry(self, config_entry_id: str) -> ConfigEntry:
        """Return config entry or raise if not found."""
        entry = self.hass.config_entries.async_get_entry(config_entry_id)
        if entry is None:
            raise UnknownEntry(config_entry_id)

        return entry

    async def async_create_flow(
        self,
        handler_key: str,
        *,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> OptionsFlow:
        """Create an options flow for a config entry.

        Entry_id and flow.handler is the same thing to map entry with flow.
        """
        entry = self._async_get_config_entry(handler_key)
        handler = await _async_get_flow_handler(self.hass, entry.domain, {})
        return handler.async_get_options_flow(entry)

    async def async_finish_flow(
        self, flow: data_entry_flow.FlowHandler, result: data_entry_flow.FlowResult
    ) -> data_entry_flow.FlowResult:
        """Finish an options flow and update options for configuration entry.

        Flow.handler and entry_id is the same thing to map flow with entry.
        """
        flow = cast(OptionsFlow, flow)

        if result["type"] != data_entry_flow.FlowResultType.CREATE_ENTRY:
            return result

        entry = self.hass.config_entries.async_get_entry(flow.handler)
        if entry is None:
            raise UnknownEntry(flow.handler)
        if result["data"] is not None:
            self.hass.config_entries.async_update_entry(entry, options=result["data"])

        result["result"] = True
        return result

    async def _async_setup_preview(self, flow: data_entry_flow.FlowHandler) -> None:
        """Set up preview for an option flow handler."""
        entry = self._async_get_config_entry(flow.handler)
        await _load_integration(self.hass, entry.domain, {})
        if entry.domain not in self._preview:
            self._preview.add(entry.domain)
            await flow.async_setup_preview(self.hass)


class OptionsFlow(data_entry_flow.FlowHandler):
    """Base class for config options flows."""

    handler: str

    @callback
    def _async_abort_entries_match(
        self, match_dict: dict[str, Any] | None = None
    ) -> None:
        """Abort if another current entry matches all data.

        Requires `already_configured` in strings.json in user visible flows.
        """

        config_entry = cast(
            ConfigEntry, self.hass.config_entries.async_get_entry(self.handler)
        )
        _async_abort_entries_match(
            [
                entry
                for entry in self.hass.config_entries.async_entries(config_entry.domain)
                if entry is not config_entry and entry.source != SOURCE_IGNORE
            ],
            match_dict,
        )


class OptionsFlowWithConfigEntry(OptionsFlow):
    """Base class for options flows with config entry and options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._options = deepcopy(dict(config_entry.options))

    @property
    def config_entry(self) -> ConfigEntry:
        """Return the config entry."""
        return self._config_entry

    @property
    def options(self) -> dict[str, Any]:
        """Return a mutable copy of the config entry options."""
        return self._options


class EntityRegistryDisabledHandler:
    """Handler when entities related to config entries updated disabled_by."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the handler."""
        self.hass = hass
        self.registry: entity_registry.EntityRegistry | None = None
        self.changed: set[str] = set()
        self._remove_call_later: Callable[[], None] | None = None

    @callback
    def async_setup(self) -> None:
        """Set up the disable handler."""
        self.hass.bus.async_listen(
            entity_registry.EVENT_ENTITY_REGISTRY_UPDATED,
            self._handle_entry_updated,
            event_filter=_handle_entry_updated_filter,
        )

    async def _handle_entry_updated(self, event: Event) -> None:
        """Handle entity registry entry update."""
        if self.registry is None:
            self.registry = entity_registry.async_get(self.hass)

        entity_entry = self.registry.async_get(event.data["entity_id"])

        if (
            # Stop if no entry found
            entity_entry is None
            # Stop if entry not connected to config entry
            or entity_entry.config_entry_id is None
            # Stop if the entry got disabled. In that case the entity handles it
            # themselves.
            or entity_entry.disabled_by
        ):
            return

        config_entry = self.hass.config_entries.async_get_entry(
            entity_entry.config_entry_id
        )
        assert config_entry is not None

        if config_entry.entry_id not in self.changed and config_entry.supports_unload:
            self.changed.add(config_entry.entry_id)

        if not self.changed:
            return

        # We are going to delay reloading on *every* entity registry change so that
        # if a user is happily clicking along, it will only reload at the end.

        if self._remove_call_later:
            self._remove_call_later()

        self._remove_call_later = async_call_later(
            self.hass,
            RELOAD_AFTER_UPDATE_DELAY,
            HassJob(self._handle_reload, cancel_on_shutdown=True),
        )

    async def _handle_reload(self, _now: Any) -> None:
        """Handle a reload."""
        self._remove_call_later = None
        to_reload = self.changed
        self.changed = set()

        _LOGGER.info(
            (
                "Reloading configuration entries because disabled_by changed in entity"
                " registry: %s"
            ),
            ", ".join(to_reload),
        )

        await asyncio.gather(
            *(
                asyncio.create_task(
                    self.hass.config_entries.async_reload(entry_id),
                    name="config entry reload {entry.title} {entry.domain} {entry.entry_id}",
                )
                for entry_id in to_reload
            )
        )


@callback
def _handle_entry_updated_filter(event: Event) -> bool:
    """Handle entity registry entry update filter.

    Only handle changes to "disabled_by".
    If "disabled_by" was CONFIG_ENTRY, reload is not needed.
    """
    if (
        event.data["action"] != "update"
        or "disabled_by" not in event.data["changes"]
        or event.data["changes"]["disabled_by"]
        is entity_registry.RegistryEntryDisabler.CONFIG_ENTRY
    ):
        return False
    return True


async def support_entry_unload(hass: HomeAssistant, domain: str) -> bool:
    """Test if a domain supports entry unloading."""
    integration = await loader.async_get_integration(hass, domain)
    component = integration.get_component()
    return hasattr(component, "async_unload_entry")


async def support_remove_from_device(hass: HomeAssistant, domain: str) -> bool:
    """Test if a domain supports being removed from a device."""
    integration = await loader.async_get_integration(hass, domain)
    component = integration.get_component()
    return hasattr(component, "async_remove_config_entry_device")


async def _load_integration(
    hass: HomeAssistant, domain: str, hass_config: ConfigType
) -> None:
    try:
        integration = await loader.async_get_integration(hass, domain)
    except loader.IntegrationNotFound as err:
        _LOGGER.error("Cannot find integration %s", domain)
        raise data_entry_flow.UnknownHandler from err

    # Make sure requirements and dependencies of component are resolved
    await async_process_deps_reqs(hass, hass_config, integration)

    try:
        integration.get_platform("config_flow")
    except ImportError as err:
        _LOGGER.error(
            "Error occurred loading flow for integration %s: %s",
            domain,
            err,
        )
        raise data_entry_flow.UnknownHandler


async def _async_get_flow_handler(
    hass: HomeAssistant, domain: str, hass_config: ConfigType
) -> type[ConfigFlow]:
    """Get a flow handler for specified domain."""

    # First check if there is a handler registered for the domain
    if domain in hass.config.components and (handler := HANDLERS.get(domain)):
        return handler

    await _load_integration(hass, domain, hass_config)

    if handler := HANDLERS.get(domain):
        return handler

    raise data_entry_flow.UnknownHandler
