"""Manage config entries in Home Assistant."""

from __future__ import annotations

import asyncio
from collections import UserDict
from collections.abc import (
    Callable,
    Coroutine,
    Generator,
    Hashable,
    Iterable,
    Mapping,
    ValuesView,
)
from contextvars import ContextVar
from copy import deepcopy
from enum import Enum, StrEnum
import functools
from functools import cached_property
import logging
from random import randint
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Generic, Self, cast

from async_interrupt import interrupt
from typing_extensions import TypeVar

from . import data_entry_flow, loader
from .components import persistent_notification
from .const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP, Platform
from .core import (
    CALLBACK_TYPE,
    DOMAIN as HA_DOMAIN,
    CoreState,
    Event,
    HassJob,
    HassJobType,
    HomeAssistant,
    callback,
)
from .data_entry_flow import FLOW_NOT_COMPLETE_STEPS, FlowResult
from .exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from .helpers import device_registry, entity_registry, issue_registry as ir, storage
from .helpers.debounce import Debouncer
from .helpers.dispatcher import SignalType, async_dispatcher_send_internal
from .helpers.event import (
    RANDOM_MICROSECOND_MAX,
    RANDOM_MICROSECOND_MIN,
    async_call_later,
)
from .helpers.frame import report
from .helpers.json import json_bytes, json_fragment
from .helpers.typing import UNDEFINED, ConfigType, DiscoveryInfoType, UndefinedType
from .loader import async_suggest_report_issue
from .setup import (
    DATA_SETUP_DONE,
    SetupPhases,
    async_pause_setup,
    async_process_deps_reqs,
    async_setup_component,
    async_start_setup,
)
from .util import ulid as ulid_util
from .util.async_ import create_eager_task
from .util.decorator import Registry
from .util.enum import try_parse_enum

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
SOURCE_HARDWARE = "hardware"
SOURCE_HASSIO = "hassio"
SOURCE_HOMEKIT = "homekit"
SOURCE_IMPORT = "import"
SOURCE_INTEGRATION_DISCOVERY = "integration_discovery"
SOURCE_MQTT = "mqtt"
SOURCE_SSDP = "ssdp"
SOURCE_SYSTEM = "system"
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

# This is used to initiate a reconfigure flow by the user.
SOURCE_RECONFIGURE = "reconfigure"

HANDLERS: Registry[str, type[ConfigFlow]] = Registry()

STORAGE_KEY = "core.config_entries"
STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 2

SAVE_DELAY = 1

DISCOVERY_COOLDOWN = 1

_DataT = TypeVar("_DataT", default=Any)


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
        obj._recoverable = recoverable  # noqa: SLF001
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
    SOURCE_HARDWARE,
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

SIGNAL_CONFIG_ENTRY_CHANGED = SignalType["ConfigEntryChange", "ConfigEntry"](
    "config_entry_changed"
)

NO_RESET_TRIES_STATES = {
    ConfigEntryState.SETUP_RETRY,
    ConfigEntryState.SETUP_IN_PROGRESS,
}


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


type UpdateListenerType = Callable[
    [HomeAssistant, ConfigEntry], Coroutine[Any, Any, None]
]

FROZEN_CONFIG_ENTRY_ATTRS = {
    "entry_id",
    "domain",
    "state",
    "reason",
    "error_reason_translation_key",
    "error_reason_translation_placeholders",
}
UPDATE_ENTRY_CONFIG_ENTRY_ATTRS = {
    "unique_id",
    "title",
    "data",
    "options",
    "pref_disable_new_entities",
    "pref_disable_polling",
    "minor_version",
    "version",
}


class ConfigFlowResult(FlowResult, total=False):
    """Typed result dict for config flow."""

    minor_version: int
    options: Mapping[str, Any]
    version: int


class ConfigEntry(Generic[_DataT]):
    """Hold a configuration entry."""

    entry_id: str
    domain: str
    title: str
    data: MappingProxyType[str, Any]
    runtime_data: _DataT
    options: MappingProxyType[str, Any]
    unique_id: str | None
    state: ConfigEntryState
    reason: str | None
    error_reason_translation_key: str | None
    error_reason_translation_placeholders: dict[str, Any] | None
    pref_disable_new_entities: bool
    pref_disable_polling: bool
    version: int
    source: str
    minor_version: int
    disabled_by: ConfigEntryDisabler | None
    supports_unload: bool | None
    supports_remove_device: bool | None
    _supports_options: bool | None
    _supports_reconfigure: bool | None
    update_listeners: list[UpdateListenerType]
    _async_cancel_retry_setup: Callable[[], Any] | None
    _on_unload: list[Callable[[], Coroutine[Any, Any, None] | None]] | None
    setup_lock: asyncio.Lock
    _reauth_lock: asyncio.Lock
    _reconfigure_lock: asyncio.Lock
    _tasks: set[asyncio.Future[Any]]
    _background_tasks: set[asyncio.Future[Any]]
    _integration_for_domain: loader.Integration | None
    _tries: int

    def __init__(
        self,
        *,
        data: Mapping[str, Any],
        disabled_by: ConfigEntryDisabler | None = None,
        domain: str,
        entry_id: str | None = None,
        minor_version: int,
        options: Mapping[str, Any] | None,
        pref_disable_new_entities: bool | None = None,
        pref_disable_polling: bool | None = None,
        source: str,
        state: ConfigEntryState = ConfigEntryState.NOT_LOADED,
        title: str,
        unique_id: str | None,
        version: int,
    ) -> None:
        """Initialize a config entry."""
        _setter = object.__setattr__
        # Unique id of the config entry
        _setter(self, "entry_id", entry_id or ulid_util.ulid_now())

        # Version of the configuration.
        _setter(self, "version", version)
        _setter(self, "minor_version", minor_version)

        # Domain the configuration belongs to
        _setter(self, "domain", domain)

        # Title of the configuration
        _setter(self, "title", title)

        # Config data
        _setter(self, "data", MappingProxyType(data))

        # Entry options
        _setter(self, "options", MappingProxyType(options or {}))

        # Entry system options
        if pref_disable_new_entities is None:
            pref_disable_new_entities = False

        _setter(self, "pref_disable_new_entities", pref_disable_new_entities)

        if pref_disable_polling is None:
            pref_disable_polling = False

        _setter(self, "pref_disable_polling", pref_disable_polling)

        # Source of the configuration (user, discovery, cloud)
        _setter(self, "source", source)

        # State of the entry (LOADED, NOT_LOADED)
        _setter(self, "state", state)

        # Unique ID of this entry.
        _setter(self, "unique_id", unique_id)

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
        _setter(self, "disabled_by", disabled_by)

        # Supports unload
        _setter(self, "supports_unload", None)

        # Supports remove device
        _setter(self, "supports_remove_device", None)

        # Supports options
        _setter(self, "_supports_options", None)

        # Supports reconfigure
        _setter(self, "_supports_reconfigure", None)

        # Listeners to call on update
        _setter(self, "update_listeners", [])

        # Reason why config entry is in a failed state
        _setter(self, "reason", None)
        _setter(self, "error_reason_translation_key", None)
        _setter(self, "error_reason_translation_placeholders", None)

        # Function to cancel a scheduled retry
        _setter(self, "_async_cancel_retry_setup", None)

        # Hold list for actions to call on unload.
        _setter(self, "_on_unload", None)

        # Reload lock to prevent conflicting reloads
        _setter(self, "setup_lock", asyncio.Lock())
        # Reauth lock to prevent concurrent reauth flows
        _setter(self, "_reauth_lock", asyncio.Lock())
        # Reconfigure lock to prevent concurrent reconfigure flows
        _setter(self, "_reconfigure_lock", asyncio.Lock())

        _setter(self, "_tasks", set())
        _setter(self, "_background_tasks", set())

        _setter(self, "_integration_for_domain", None)
        _setter(self, "_tries", 0)

    def __repr__(self) -> str:
        """Representation of ConfigEntry."""
        return (
            f"<ConfigEntry entry_id={self.entry_id} version={self.version} domain={self.domain} "
            f"title={self.title} state={self.state} unique_id={self.unique_id}>"
        )

    def __setattr__(self, key: str, value: Any) -> None:
        """Set an attribute."""
        if key in UPDATE_ENTRY_CONFIG_ENTRY_ATTRS:
            if key == "unique_id":
                # Setting unique_id directly will corrupt internal state
                # There is no deprecation period for this key
                # as changing them will corrupt internal state
                # so we raise an error here
                raise AttributeError(
                    "unique_id cannot be changed directly, use async_update_entry instead"
                )
            report(
                f'sets "{key}" directly to update a config entry. This is deprecated and will'
                " stop working in Home Assistant 2024.9, it should be updated to use"
                " async_update_entry instead",
                error_if_core=False,
            )

        elif key in FROZEN_CONFIG_ENTRY_ATTRS:
            # These attributes are frozen and cannot be changed
            # There is no deprecation period for these
            # as changing them will corrupt internal state
            # so we raise an error here
            raise AttributeError(f"{key} cannot be changed")

        super().__setattr__(key, value)
        self.clear_cache()

    @property
    def supports_options(self) -> bool:
        """Return if entry supports config options."""
        if self._supports_options is None and (handler := HANDLERS.get(self.domain)):
            # work out if handler has support for options flow
            object.__setattr__(
                self, "_supports_options", handler.async_supports_options_flow(self)
            )
        return self._supports_options or False

    @property
    def supports_reconfigure(self) -> bool:
        """Return if entry supports reconfigure step."""
        if self._supports_reconfigure is None and (
            handler := HANDLERS.get(self.domain)
        ):
            # work out if handler has support for reconfigure step
            object.__setattr__(
                self,
                "_supports_reconfigure",
                hasattr(handler, "async_step_reconfigure"),
            )
        return self._supports_reconfigure or False

    def clear_cache(self) -> None:
        """Clear cached properties."""
        self.__dict__.pop("as_json_fragment", None)

    @cached_property
    def as_json_fragment(self) -> json_fragment:
        """Return JSON fragment of a config entry."""
        json_repr = {
            "entry_id": self.entry_id,
            "domain": self.domain,
            "title": self.title,
            "source": self.source,
            "state": self.state.value,
            "supports_options": self.supports_options,
            "supports_remove_device": self.supports_remove_device or False,
            "supports_unload": self.supports_unload or False,
            "supports_reconfigure": self.supports_reconfigure,
            "pref_disable_new_entities": self.pref_disable_new_entities,
            "pref_disable_polling": self.pref_disable_polling,
            "disabled_by": self.disabled_by,
            "reason": self.reason,
            "error_reason_translation_key": self.error_reason_translation_key,
            "error_reason_translation_placeholders": self.error_reason_translation_placeholders,
        }
        return json_fragment(json_bytes(json_repr))

    async def async_setup(
        self,
        hass: HomeAssistant,
        *,
        integration: loader.Integration | None = None,
    ) -> None:
        """Set up an entry."""
        current_entry.set(self)
        if self.source == SOURCE_IGNORE or self.disabled_by:
            return

        if integration is None and not (integration := self._integration_for_domain):
            integration = await loader.async_get_integration(hass, self.domain)
            self._integration_for_domain = integration

        # Only store setup result as state if it was not forwarded.
        if domain_is_integration := self.domain == integration.domain:
            if self.state in (
                ConfigEntryState.LOADED,
                ConfigEntryState.SETUP_IN_PROGRESS,
            ):
                raise OperationNotAllowed(
                    f"The config entry {self.title} ({self.domain}) with entry_id"
                    f" {self.entry_id} cannot be set up because it is already loaded "
                    f"in the {self.state} state"
                )
            if not self.setup_lock.locked():
                raise OperationNotAllowed(
                    f"The config entry {self.title} ({self.domain}) with entry_id"
                    f" {self.entry_id} cannot be set up because it does not hold "
                    "the setup lock"
                )
            self._async_set_state(hass, ConfigEntryState.SETUP_IN_PROGRESS, None)

        if self.supports_unload is None:
            self.supports_unload = await support_entry_unload(hass, self.domain)
        if self.supports_remove_device is None:
            self.supports_remove_device = await support_remove_from_device(
                hass, self.domain
            )
        try:
            component = await integration.async_get_component()
        except ImportError as err:
            _LOGGER.error(
                "Error importing integration %s to set up %s configuration entry: %s",
                integration.domain,
                self.domain,
                err,
            )
            if domain_is_integration:
                self._async_set_state(
                    hass, ConfigEntryState.SETUP_ERROR, "Import error"
                )
            return

        if domain_is_integration:
            try:
                await integration.async_get_platform("config_flow")
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

            setup_phase = SetupPhases.CONFIG_ENTRY_SETUP
        else:
            setup_phase = SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP

        error_reason = None
        error_reason_translation_key = None
        error_reason_translation_placeholders = None

        try:
            with async_start_setup(
                hass, integration=self.domain, group=self.entry_id, phase=setup_phase
            ):
                result = await component.async_setup_entry(hass, self)

            if not isinstance(result, bool):
                _LOGGER.error(  # type: ignore[unreachable]
                    "%s.async_setup_entry did not return boolean", integration.domain
                )
                result = False
        except ConfigEntryError as exc:
            error_reason = str(exc) or "Unknown fatal config entry error"
            error_reason_translation_key = exc.translation_key
            error_reason_translation_placeholders = exc.translation_placeholders
            _LOGGER.exception(
                "Error setting up entry %s for %s: %s",
                self.title,
                self.domain,
                error_reason,
            )
            await self._async_process_on_unload(hass)
            result = False
        except ConfigEntryAuthFailed as exc:
            message = str(exc)
            auth_base_message = "could not authenticate"
            error_reason = message or auth_base_message
            error_reason_translation_key = exc.translation_key
            error_reason_translation_placeholders = exc.translation_placeholders
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
        except ConfigEntryNotReady as exc:
            message = str(exc)
            error_reason_translation_key = exc.translation_key
            error_reason_translation_placeholders = exc.translation_placeholders
            self._async_set_state(
                hass,
                ConfigEntryState.SETUP_RETRY,
                message or None,
                error_reason_translation_key,
                error_reason_translation_placeholders,
            )
            wait_time = 2 ** min(self._tries, 4) * 5 + (
                randint(RANDOM_MICROSECOND_MIN, RANDOM_MICROSECOND_MAX) / 1000000
            )
            self._tries += 1
            ready_message = f"ready yet: {message}" if message else "ready yet"
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

            if hass.state is CoreState.running:
                self._async_cancel_retry_setup = async_call_later(
                    hass,
                    wait_time,
                    HassJob(
                        functools.partial(self._async_setup_again, hass),
                        job_type=HassJobType.Callback,
                        cancel_on_shutdown=True,
                    ),
                )
            else:
                self._async_cancel_retry_setup = hass.bus.async_listen(
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

        #
        # After successfully calling async_setup_entry, it is important that this function
        # does not yield to the event loop by using `await` or `async with` or
        # similar until after the state has been set by calling self._async_set_state.
        #
        # Otherwise we risk that any `call_soon`s
        # created by an integration will be executed before the state is set.
        #

        # Only store setup result as state if it was not forwarded.
        if not domain_is_integration:
            return

        self.async_cancel_retry_setup()

        if result:
            self._async_set_state(hass, ConfigEntryState.LOADED, None)
        else:
            self._async_set_state(
                hass,
                ConfigEntryState.SETUP_ERROR,
                error_reason,
                error_reason_translation_key,
                error_reason_translation_placeholders,
            )

    @callback
    def _async_setup_again(self, hass: HomeAssistant, *_: Any) -> None:
        """Schedule setup again.

        This method is a callback to ensure that _async_cancel_retry_setup
        is unset as soon as its callback is called.
        """
        self._async_cancel_retry_setup = None
        # Check again when we fire in case shutdown
        # has started so we do not block shutdown
        if not hass.is_stopping:
            hass.async_create_background_task(
                self.async_setup_locked(hass),
                f"config entry retry {self.domain} {self.title}",
                eager_start=True,
            )

    async def async_setup_locked(
        self, hass: HomeAssistant, integration: loader.Integration | None = None
    ) -> None:
        """Set up while holding the setup lock."""
        async with self.setup_lock:
            if self.state is ConfigEntryState.LOADED:
                # If something loaded the config entry while
                # we were waiting for the lock, we should not
                # set it up again.
                _LOGGER.debug(
                    "Not setting up %s (%s %s) again, already loaded",
                    self.title,
                    self.domain,
                    self.entry_id,
                )
                return
            await self.async_setup(hass, integration=integration)

    @callback
    def async_shutdown(self) -> None:
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

        component = await integration.async_get_component()

        if domain_is_integration := self.domain == integration.domain:
            if not self.setup_lock.locked():
                raise OperationNotAllowed(
                    f"The config entry {self.title} ({self.domain}) with entry_id"
                    f" {self.entry_id} cannot be unloaded because it does not hold "
                    "the setup lock"
                )

            if not self.state.recoverable:
                return False

            if self.state is not ConfigEntryState.LOADED:
                self.async_cancel_retry_setup()
                self._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
                return True

        supports_unload = hasattr(component, "async_unload_entry")

        if not supports_unload:
            if domain_is_integration:
                self._async_set_state(
                    hass, ConfigEntryState.FAILED_UNLOAD, "Unload not supported"
                )
            return False

        try:
            result = await component.async_unload_entry(hass, self)

            assert isinstance(result, bool)

            # Only adjust state if we unloaded the component
            if domain_is_integration and result:
                await self._async_process_on_unload(hass)
                if hasattr(self, "runtime_data"):
                    object.__delattr__(self, "runtime_data")

                self._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)

        except Exception as exc:
            _LOGGER.exception(
                "Error unloading entry %s for %s", self.title, integration.domain
            )
            if domain_is_integration:
                self._async_set_state(
                    hass, ConfigEntryState.FAILED_UNLOAD, str(exc) or "Unknown error"
                )
            return False
        return result

    async def async_remove(self, hass: HomeAssistant) -> None:
        """Invoke remove callback on component."""
        if self.source == SOURCE_IGNORE:
            return

        if not self.setup_lock.locked():
            raise OperationNotAllowed(
                f"The config entry {self.title} ({self.domain}) with entry_id"
                f" {self.entry_id} cannot be removed because it does not hold "
                "the setup lock"
            )

        if not (integration := self._integration_for_domain):
            try:
                integration = await loader.async_get_integration(hass, self.domain)
            except loader.IntegrationNotFound:
                # The integration was likely a custom_component
                # that was uninstalled, or an integration
                # that has been renamed without removing the config
                # entry.
                return

        component = await integration.async_get_component()
        if not hasattr(component, "async_remove_entry"):
            return
        try:
            await component.async_remove_entry(hass, self)
        except Exception:
            _LOGGER.exception(
                "Error calling entry remove callback %s for %s",
                self.title,
                integration.domain,
            )

    @callback
    def _async_set_state(
        self,
        hass: HomeAssistant,
        state: ConfigEntryState,
        reason: str | None,
        error_reason_translation_key: str | None = None,
        error_reason_translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Set the state of the config entry."""
        if state not in NO_RESET_TRIES_STATES:
            self._tries = 0
        _setter = object.__setattr__
        _setter(self, "state", state)
        _setter(self, "reason", reason)
        _setter(self, "error_reason_translation_key", error_reason_translation_key)
        _setter(
            self,
            "error_reason_translation_placeholders",
            error_reason_translation_placeholders,
        )
        self.clear_cache()
        async_dispatcher_send_internal(
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

        same_major_version = self.version == handler.VERSION
        if same_major_version and self.minor_version == handler.MINOR_VERSION:
            return True

        if not (integration := self._integration_for_domain):
            integration = await loader.async_get_integration(hass, self.domain)
        component = await integration.async_get_component()
        supports_migrate = hasattr(component, "async_migrate_entry")
        if not supports_migrate:
            if same_major_version:
                return True
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
                hass.config_entries._async_schedule_save()  # noqa: SLF001
        except Exception:
            _LOGGER.exception(
                "Error migrating entry %s for %s", self.title, self.domain
            )
            return False
        return result

    def add_update_listener(self, listener: UpdateListenerType) -> CALLBACK_TYPE:
        """Listen for when entry is updated.

        Returns function to unlisten.
        """
        self.update_listeners.append(listener)
        return lambda: self.update_listeners.remove(listener)

    def as_dict(self) -> dict[str, Any]:
        """Return dictionary version of this entry."""
        return {
            "data": dict(self.data),
            "disabled_by": self.disabled_by,
            "domain": self.domain,
            "entry_id": self.entry_id,
            "minor_version": self.minor_version,
            "options": dict(self.options),
            "pref_disable_new_entities": self.pref_disable_new_entities,
            "pref_disable_polling": self.pref_disable_polling,
            "source": self.source,
            "title": self.title,
            "unique_id": self.unique_id,
            "version": self.version,
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
                    self.async_create_task(hass, job, eager_start=True)

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
        # We will check this again in the task when we hold the lock,
        # but we also check it now to try to avoid creating the task.
        if any(self.async_get_active_flows(hass, {SOURCE_RECONFIGURE, SOURCE_REAUTH})):
            # Reauth or Reconfigure flow already in progress for this entry
            return
        hass.async_create_task(
            self._async_init_reauth(hass, context, data),
            f"config entry reauth {self.title} {self.domain} {self.entry_id}",
            eager_start=True,
        )

    async def _async_init_reauth(
        self,
        hass: HomeAssistant,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Start a reauth flow."""
        async with self._reauth_lock:
            if any(
                self.async_get_active_flows(hass, {SOURCE_RECONFIGURE, SOURCE_REAUTH})
            ):
                # Reauth or Reconfigure flow already in progress for this entry
                return
            result = await hass.config_entries.flow.async_init(
                self.domain,
                context={
                    "source": SOURCE_REAUTH,
                    "entry_id": self.entry_id,
                    "title_placeholders": {"name": self.title},
                    "unique_id": self.unique_id,
                }
                | (context or {}),
                data=self.data | (data or {}),
            )
        if result["type"] not in FLOW_NOT_COMPLETE_STEPS:
            return

        # Create an issue, there's no need to hold the lock when doing that
        issue_id = f"config_entry_reauth_{self.domain}_{self.entry_id}"
        ir.async_create_issue(
            hass,
            HA_DOMAIN,
            issue_id,
            data={"flow_id": result["flow_id"]},
            is_fixable=False,
            issue_domain=self.domain,
            severity=ir.IssueSeverity.ERROR,
            translation_key="config_entry_reauth",
            translation_placeholders={"name": self.title},
        )

    @callback
    def async_start_reconfigure(
        self,
        hass: HomeAssistant,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Start a reconfigure flow."""
        # We will check this again in the task when we hold the lock,
        # but we also check it now to try to avoid creating the task.
        if any(self.async_get_active_flows(hass, {SOURCE_RECONFIGURE, SOURCE_REAUTH})):
            # Reconfigure or reauth flow already in progress for this entry
            return
        hass.async_create_task(
            self._async_init_reconfigure(hass, context, data),
            f"config entry reconfigure {self.title} {self.domain} {self.entry_id}",
        )

    async def _async_init_reconfigure(
        self,
        hass: HomeAssistant,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Start a reconfigure flow."""
        async with self._reconfigure_lock:
            if any(
                self.async_get_active_flows(hass, {SOURCE_RECONFIGURE, SOURCE_REAUTH})
            ):
                # Reconfigure or reauth flow already in progress for this entry
                return
            await hass.config_entries.flow.async_init(
                self.domain,
                context={
                    "source": SOURCE_RECONFIGURE,
                    "entry_id": self.entry_id,
                    "title_placeholders": {"name": self.title},
                    "unique_id": self.unique_id,
                }
                | (context or {}),
                data=self.data | (data or {}),
            )

    @callback
    def async_get_active_flows(
        self, hass: HomeAssistant, sources: set[str]
    ) -> Generator[ConfigFlowResult]:
        """Get any active flows of certain sources for this entry."""
        return (
            flow
            for flow in hass.config_entries.flow.async_progress_by_handler(
                self.domain,
                match_context={"entry_id": self.entry_id},
                include_uninitialized=True,
            )
            if flow["context"].get("source") in sources
        )

    @callback
    def async_create_task[_R](
        self,
        hass: HomeAssistant,
        target: Coroutine[Any, Any, _R],
        name: str | None = None,
        eager_start: bool = True,
    ) -> asyncio.Task[_R]:
        """Create a task from within the event loop.

        This method must be run in the event loop.

        target: target to call.
        """
        task = hass.async_create_task_internal(
            target, f"{name} {self.title} {self.domain} {self.entry_id}", eager_start
        )
        if eager_start and task.done():
            return task
        self._tasks.add(task)
        task.add_done_callback(self._tasks.remove)

        return task

    @callback
    def async_create_background_task[_R](
        self,
        hass: HomeAssistant,
        target: Coroutine[Any, Any, _R],
        name: str,
        eager_start: bool = True,
    ) -> asyncio.Task[_R]:
        """Create a background task tied to the config entry lifecycle.

        Background tasks are automatically canceled when config entry is unloaded.

        A background task is different from a normal task:

          - Will not block startup
          - Will be automatically cancelled on shutdown
          - Calls to async_block_till_done will not wait for completion

        This method must be run in the event loop.
        """
        task = hass.async_create_background_task(target, name, eager_start)
        if task.done():
            return task
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.remove)
        return task


current_entry: ContextVar[ConfigEntry | None] = ContextVar(
    "current_entry", default=None
)


class FlowCancelledError(Exception):
    """Error to indicate that a flow has been cancelled."""


def _report_non_awaited_platform_forwards(entry: ConfigEntry, what: str) -> None:
    """Report non awaited platform forwards."""
    report(
        f"calls {what} for integration {entry.domain} with "
        f"title: {entry.title} and entry_id: {entry.entry_id}, "
        f"during setup without awaiting {what}, which can cause "
        "the setup lock to be released before the setup is done. "
        "This will stop working in Home Assistant 2025.1",
        error_if_integration=False,
        error_if_core=False,
    )


class ConfigEntriesFlowManager(data_entry_flow.FlowManager[ConfigFlowResult]):
    """Manage all the config entry flows that are in progress."""

    _flow_result = ConfigFlowResult

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
        self._initialize_futures: dict[str, list[asyncio.Future[None]]] = {}
        self._discovery_debouncer = Debouncer[None](
            hass,
            _LOGGER,
            cooldown=DISCOVERY_COOLDOWN,
            immediate=True,
            function=self._async_discovery,
            background=True,
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
    ) -> ConfigFlowResult:
        """Start a configuration flow."""
        if not context or "source" not in context:
            raise KeyError("Context not set or doesn't have a source set")

        flow_id = ulid_util.ulid_now()

        # Avoid starting a config flow on an integration that only supports
        # a single config entry, but which already has an entry
        if (
            context.get("source")
            not in {SOURCE_IGNORE, SOURCE_REAUTH, SOURCE_UNIGNORE, SOURCE_RECONFIGURE}
            and self.config_entries.async_has_entries(handler, include_ignore=False)
            and await _support_single_config_entry_only(self.hass, handler)
        ):
            return ConfigFlowResult(
                type=data_entry_flow.FlowResultType.ABORT,
                flow_id=flow_id,
                handler=handler,
                reason="single_instance_allowed",
                translation_domain=HA_DOMAIN,
            )

        loop = self.hass.loop

        if context["source"] == SOURCE_IMPORT:
            self._pending_import_flows.setdefault(handler, {})[flow_id] = (
                loop.create_future()
            )

        cancel_init_future = loop.create_future()
        self._initialize_futures.setdefault(handler, []).append(cancel_init_future)
        try:
            async with interrupt(
                cancel_init_future,
                FlowCancelledError,
                "Config entry initialize canceled: Home Assistant is shutting down",
            ):
                flow, result = await self._async_init(flow_id, handler, context, data)
        except FlowCancelledError as ex:
            raise asyncio.CancelledError from ex
        finally:
            self._initialize_futures[handler].remove(cancel_init_future)
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
    ) -> tuple[ConfigFlow, ConfigFlowResult]:
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

    @callback
    def async_shutdown(self) -> None:
        """Cancel any initializing flows."""
        for future_list in self._initialize_futures.values():
            for future in future_list:
                future.set_result(None)
        self._discovery_debouncer.async_shutdown()

    async def async_finish_flow(
        self,
        flow: data_entry_flow.FlowHandler[ConfigFlowResult],
        result: ConfigFlowResult,
    ) -> ConfigFlowResult:
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

        # Clean up issue if this is a reauth flow
        if flow.context["source"] == SOURCE_REAUTH:
            if (entry_id := flow.context.get("entry_id")) is not None and (
                entry := self.config_entries.async_get_entry(entry_id)
            ) is not None:
                issue_id = f"config_entry_reauth_{entry.domain}_{entry.entry_id}"
                ir.async_delete_issue(self.hass, HA_DOMAIN, issue_id)

        if result["type"] != data_entry_flow.FlowResultType.CREATE_ENTRY:
            return result

        # Avoid adding a config entry for a integration
        # that only supports a single config entry, but already has an entry
        if (
            self.config_entries.async_has_entries(flow.handler, include_ignore=False)
            and await _support_single_config_entry_only(self.hass, flow.handler)
            and flow.context["source"] != SOURCE_IGNORE
        ):
            return ConfigFlowResult(
                type=data_entry_flow.FlowResultType.ABORT,
                flow_id=flow.flow_id,
                handler=flow.handler,
                reason="single_instance_allowed",
                translation_domain=HA_DOMAIN,
            )

        # Check if config entry exists with unique ID. Unload it.
        existing_entry = None

        # Abort all flows in progress with same unique ID
        # or the default discovery ID
        for progress_flow in self.async_progress_by_handler(flow.handler):
            progress_unique_id = progress_flow["context"].get("unique_id")
            progress_flow_id = progress_flow["flow_id"]

            if progress_flow_id != flow.flow_id and (
                (flow.unique_id and progress_unique_id == flow.unique_id)
                or progress_unique_id == DEFAULT_DISCOVERY_UNIQUE_ID
            ):
                self.async_abort(progress_flow_id)

            # Abort any flows in progress for the same handler
            # when integration allows only one config entry
            if (
                progress_flow_id != flow.flow_id
                and await _support_single_config_entry_only(self.hass, flow.handler)
            ):
                self.async_abort(progress_flow_id)

        if flow.unique_id is not None:
            # Reset unique ID when the default discovery ID has been used
            if flow.unique_id == DEFAULT_DISCOVERY_UNIQUE_ID:
                await flow.async_set_unique_id(None)

            # Find existing entry.
            existing_entry = self.config_entries.async_entry_for_domain_unique_id(
                result["handler"], flow.unique_id
            )

        # Unload the entry before setting up the new one.
        # We will remove it only after the other one is set up,
        # so that device customizations are not getting lost.
        if existing_entry is not None and existing_entry.state.recoverable:
            await self.config_entries.async_unload(existing_entry.entry_id)

        entry = ConfigEntry(
            data=result["data"],
            domain=result["handler"],
            minor_version=result["minor_version"],
            options=result["options"],
            source=flow.context["source"],
            title=result["title"],
            unique_id=flow.unique_id,
            version=result["version"],
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
        self,
        flow: data_entry_flow.FlowHandler[ConfigFlowResult],
        result: ConfigFlowResult,
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
        # async_fire_internal is used here because this is only
        # called from the Debouncer so we know the usage is safe
        self.hass.bus.async_fire_internal(EVENT_FLOW_DISCOVERED)
        persistent_notification.async_create(
            self.hass,
            title="New devices discovered",
            message=(
                "We have discovered new devices on your network. "
                "[Check it out](/config/integrations)."
            ),
            notification_id=DISCOVERY_NOTIFICATION_ID,
        )


class ConfigEntryItems(UserDict[str, ConfigEntry]):
    """Container for config items, maps config_entry_id -> entry.

    Maintains two additional indexes:
    - domain -> list[ConfigEntry]
    - domain -> unique_id -> ConfigEntry
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the container."""
        super().__init__()
        self._hass = hass
        self._domain_index: dict[str, list[ConfigEntry]] = {}
        self._domain_unique_id_index: dict[str, dict[str, ConfigEntry]] = {}

    def values(self) -> ValuesView[ConfigEntry]:
        """Return the underlying values to avoid __iter__ overhead."""
        return self.data.values()

    def __setitem__(self, entry_id: str, entry: ConfigEntry) -> None:
        """Add an item."""
        data = self.data
        if entry_id in data:
            # This is likely a bug in a test that is adding the same entry twice.
            # In the future, once we have fixed the tests, this will raise HomeAssistantError.
            _LOGGER.error("An entry with the id %s already exists", entry_id)
            self._unindex_entry(entry_id)
        data[entry_id] = entry
        self._index_entry(entry)

    def _index_entry(self, entry: ConfigEntry) -> None:
        """Index an entry."""
        self._domain_index.setdefault(entry.domain, []).append(entry)
        if entry.unique_id is not None:
            unique_id_hash = entry.unique_id
            # Guard against integrations using unhashable unique_id
            # In HA Core 2024.9, we should remove the guard and instead fail
            if not isinstance(entry.unique_id, Hashable):
                unique_id_hash = str(entry.unique_id)  # type: ignore[unreachable]
                report_issue = async_suggest_report_issue(
                    self._hass, integration_domain=entry.domain
                )
                _LOGGER.error(
                    (
                        "Config entry '%s' from integration %s has an invalid unique_id"
                        " '%s', please %s"
                    ),
                    entry.title,
                    entry.domain,
                    entry.unique_id,
                    report_issue,
                )

            self._domain_unique_id_index.setdefault(entry.domain, {})[
                unique_id_hash
            ] = entry

    def _unindex_entry(self, entry_id: str) -> None:
        """Unindex an entry."""
        entry = self.data[entry_id]
        domain = entry.domain
        self._domain_index[domain].remove(entry)
        if not self._domain_index[domain]:
            del self._domain_index[domain]
        if (unique_id := entry.unique_id) is not None:
            # Check type first to avoid expensive isinstance call
            if type(unique_id) is not str and not isinstance(unique_id, Hashable):  # noqa: E721
                unique_id = str(entry.unique_id)  # type: ignore[unreachable]
            del self._domain_unique_id_index[domain][unique_id]
            if not self._domain_unique_id_index[domain]:
                del self._domain_unique_id_index[domain]

    def __delitem__(self, entry_id: str) -> None:
        """Remove an item."""
        self._unindex_entry(entry_id)
        super().__delitem__(entry_id)

    def update_unique_id(self, entry: ConfigEntry, new_unique_id: str | None) -> None:
        """Update unique id for an entry.

        This method mutates the entry with the new unique id and updates the indexes.
        """
        entry_id = entry.entry_id
        self._unindex_entry(entry_id)
        object.__setattr__(entry, "unique_id", new_unique_id)
        self._index_entry(entry)
        entry.clear_cache()

    def get_entries_for_domain(self, domain: str) -> list[ConfigEntry]:
        """Get entries for a domain."""
        return self._domain_index.get(domain, [])

    def get_entry_by_domain_and_unique_id(
        self, domain: str, unique_id: str
    ) -> ConfigEntry | None:
        """Get entry by domain and unique id."""
        # Check type first to avoid expensive isinstance call
        if type(unique_id) is not str and not isinstance(unique_id, Hashable):  # noqa: E721
            unique_id = str(unique_id)  # type: ignore[unreachable]
        return self._domain_unique_id_index.get(domain, {}).get(unique_id)


class ConfigEntryStore(storage.Store[dict[str, list[dict[str, Any]]]]):
    """Class to help storing config entry data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize storage class."""
        super().__init__(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            minor_version=STORAGE_VERSION_MINOR,
        )

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        data = old_data
        if old_major_version == 1 and old_minor_version < 2:
            # Version 1.2 implements migration and freezes the available keys
            for entry in data["entries"]:
                # Populate keys which were introduced before version 1.2

                pref_disable_new_entities = entry.get("pref_disable_new_entities")
                if pref_disable_new_entities is None and "system_options" in entry:
                    pref_disable_new_entities = entry.get("system_options", {}).get(
                        "disable_new_entities"
                    )

                entry.setdefault("disabled_by", entry.get("disabled_by"))
                entry.setdefault("minor_version", entry.get("minor_version", 1))
                entry.setdefault("options", entry.get("options", {}))
                entry.setdefault("pref_disable_new_entities", pref_disable_new_entities)
                entry.setdefault(
                    "pref_disable_polling", entry.get("pref_disable_polling")
                )
                entry.setdefault("unique_id", entry.get("unique_id"))

        if old_major_version > 1:
            raise NotImplementedError
        return data


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
        self._entries = ConfigEntryItems(hass)
        self._store = ConfigEntryStore(hass)
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
        return self._entries.data.get(entry_id)

    @callback
    def async_entry_ids(self) -> list[str]:
        """Return entry ids."""
        return list(self._entries.data)

    @callback
    def async_has_entries(
        self, domain: str, include_ignore: bool = True, include_disabled: bool = True
    ) -> bool:
        """Return if there are entries for a domain."""
        entries = self._entries.get_entries_for_domain(domain)
        if include_ignore and include_disabled:
            return bool(entries)
        return any(
            entry
            for entry in entries
            if (include_ignore or entry.source != SOURCE_IGNORE)
            and (include_disabled or not entry.disabled_by)
        )

    @callback
    def async_entries(
        self,
        domain: str | None = None,
        include_ignore: bool = True,
        include_disabled: bool = True,
    ) -> list[ConfigEntry]:
        """Return all entries or entries for a specific domain."""
        if domain is None:
            entries: Iterable[ConfigEntry] = self._entries.values()
        else:
            entries = self._entries.get_entries_for_domain(domain)

        if include_ignore and include_disabled:
            return list(entries)

        return [
            entry
            for entry in entries
            if (include_ignore or entry.source != SOURCE_IGNORE)
            and (include_disabled or not entry.disabled_by)
        ]

    @callback
    def async_entry_for_domain_unique_id(
        self, domain: str, unique_id: str
    ) -> ConfigEntry | None:
        """Return entry for a domain with a matching unique id."""
        return self._entries.get_entry_by_domain_and_unique_id(domain, unique_id)

    async def async_add(self, entry: ConfigEntry) -> None:
        """Add and setup an entry."""
        if entry.entry_id in self._entries.data:
            raise HomeAssistantError(
                f"An entry with the id {entry.entry_id} already exists."
            )

        self._entries[entry.entry_id] = entry
        self._async_dispatch(ConfigEntryChange.ADDED, entry)
        await self.async_setup(entry.entry_id)
        self._async_schedule_save()

    async def async_remove(self, entry_id: str) -> dict[str, Any]:
        """Remove an entry."""
        if (entry := self.async_get_entry(entry_id)) is None:
            raise UnknownEntry

        async with entry.setup_lock:
            if not entry.state.recoverable:
                unload_success = entry.state is not ConfigEntryState.FAILED_UNLOAD
            else:
                unload_success = await self.async_unload(entry_id, _lock=False)

            await entry.async_remove(self.hass)

            del self._entries[entry.entry_id]
            self._async_schedule_save()

        dev_reg = device_registry.async_get(self.hass)
        ent_reg = entity_registry.async_get(self.hass)

        dev_reg.async_clear_config_entry(entry_id)
        ent_reg.async_clear_config_entry(entry_id)

        # If the configuration entry is removed during reauth, it should
        # abort any reauth flow that is active for the removed entry and
        # linked issues.
        for progress_flow in self.hass.config_entries.flow.async_progress_by_handler(
            entry.domain, match_context={"entry_id": entry_id, "source": SOURCE_REAUTH}
        ):
            if "flow_id" in progress_flow:
                self.hass.config_entries.flow.async_abort(progress_flow["flow_id"])
                issue_id = f"config_entry_reauth_{entry.domain}_{entry.entry_id}"
                ir.async_delete_issue(self.hass, HA_DOMAIN, issue_id)

        # After we have fully removed an "ignore" config entry we can try and rediscover
        # it so that a user is able to immediately start configuring it. We do this by
        # starting a new flow with the 'unignore' step. If the integration doesn't
        # implement async_step_unignore then this will be a no-op.
        if entry.source == SOURCE_IGNORE:
            self.hass.async_create_task_internal(
                self.hass.config_entries.flow.async_init(
                    entry.domain,
                    context={"source": SOURCE_UNIGNORE},
                    data={"unique_id": entry.unique_id},
                ),
                f"config entry unignore {entry.title} {entry.domain} {entry.unique_id}",
            )

        self._async_dispatch(ConfigEntryChange.REMOVED, entry)
        return {"require_restart": not unload_success}

    @callback
    def _async_shutdown(self, event: Event) -> None:
        """Call when Home Assistant is stopping."""
        for entry in self._entries.values():
            entry.async_shutdown()
        self.flow.async_shutdown()

    async def async_initialize(self) -> None:
        """Initialize config entry config."""
        config = await self._store.async_load()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_shutdown)

        if config is None:
            self._entries = ConfigEntryItems(self.hass)
            return

        entries: ConfigEntryItems = ConfigEntryItems(self.hass)
        for entry in config["entries"]:
            entry_id = entry["entry_id"]

            config_entry = ConfigEntry(
                data=entry["data"],
                disabled_by=try_parse_enum(ConfigEntryDisabler, entry["disabled_by"]),
                domain=entry["domain"],
                entry_id=entry_id,
                minor_version=entry["minor_version"],
                options=entry["options"],
                pref_disable_new_entities=entry["pref_disable_new_entities"],
                pref_disable_polling=entry["pref_disable_polling"],
                source=entry["source"],
                title=entry["title"],
                unique_id=entry["unique_id"],
                version=entry["version"],
            )
            entries[entry_id] = config_entry

        self._entries = entries

    async def async_setup(self, entry_id: str, _lock: bool = True) -> bool:
        """Set up a config entry.

        Return True if entry has been successfully loaded.
        """
        if (entry := self.async_get_entry(entry_id)) is None:
            raise UnknownEntry

        if entry.state is not ConfigEntryState.NOT_LOADED:
            raise OperationNotAllowed(
                f"The config entry '{entry.title}' ({entry.domain}) with entry_id"
                f" '{entry.entry_id}' cannot be set up because it is in state "
                f"{entry.state}, but needs to be in the {ConfigEntryState.NOT_LOADED} state"
            )

        # Setup Component if not set up yet
        if entry.domain in self.hass.config.components:
            if _lock:
                async with entry.setup_lock:
                    await entry.async_setup(self.hass)
            else:
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

    async def async_unload(self, entry_id: str, _lock: bool = True) -> bool:
        """Unload a config entry."""
        if (entry := self.async_get_entry(entry_id)) is None:
            raise UnknownEntry

        if not entry.state.recoverable:
            raise OperationNotAllowed(
                f"The config entry '{entry.title}' ({entry.domain}) with entry_id"
                f" '{entry.entry_id}' cannot be unloaded because it is in the non"
                f" recoverable state {entry.state}"
            )

        if _lock:
            async with entry.setup_lock:
                return await entry.async_unload(self.hass)

        return await entry.async_unload(self.hass)

    @callback
    def async_schedule_reload(self, entry_id: str) -> None:
        """Schedule a config entry to be reloaded."""
        if (entry := self.async_get_entry(entry_id)) is None:
            raise UnknownEntry
        entry.async_cancel_retry_setup()
        self.hass.async_create_task(
            self.async_reload(entry_id),
            f"config entry reload {entry.title} {entry.domain} {entry.entry_id}",
        )

    async def async_reload(self, entry_id: str) -> bool:
        """Reload an entry.

        When reloading from an integration is is preferable to
        call async_schedule_reload instead of this method since
        it will cancel setup retry before starting this method
        in a task which eliminates a race condition where the
        setup retry can fire during the reload.

        If an entry was not loaded, will just load.
        """
        if (entry := self.async_get_entry(entry_id)) is None:
            raise UnknownEntry

        # Cancel the setup retry task before waiting for the
        # reload lock to reduce the chance of concurrent reload
        # attempts.
        entry.async_cancel_retry_setup()

        if entry.domain not in self.hass.config.components:
            # If the component is not loaded, just load it as
            # the config entry will be loaded as well. We need
            # to do this before holding the lock to avoid a
            # deadlock.
            await async_setup_component(self.hass, entry.domain, self._hass_config)
            return entry.state is ConfigEntryState.LOADED

        async with entry.setup_lock:
            unload_result = await self.async_unload(entry_id, _lock=False)

            if not unload_result or entry.disabled_by:
                return unload_result

            return await self.async_setup(entry_id, _lock=False)

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
        data: Mapping[str, Any] | UndefinedType = UNDEFINED,
        minor_version: int | UndefinedType = UNDEFINED,
        options: Mapping[str, Any] | UndefinedType = UNDEFINED,
        pref_disable_new_entities: bool | UndefinedType = UNDEFINED,
        pref_disable_polling: bool | UndefinedType = UNDEFINED,
        title: str | UndefinedType = UNDEFINED,
        unique_id: str | None | UndefinedType = UNDEFINED,
        version: int | UndefinedType = UNDEFINED,
    ) -> bool:
        """Update a config entry.

        If the entry was changed, the update_listeners are
        fired and this function returns True

        If the entry was not changed, the update_listeners are
        not fired and this function returns False
        """
        if entry.entry_id not in self._entries:
            raise UnknownEntry(entry.entry_id)

        self.hass.verify_event_loop_thread("hass.config_entries.async_update_entry")
        changed = False
        _setter = object.__setattr__

        if unique_id is not UNDEFINED and entry.unique_id != unique_id:
            # Reindex the entry if the unique_id has changed
            self._entries.update_unique_id(entry, unique_id)
            changed = True

        for attr, value in (
            ("minor_version", minor_version),
            ("pref_disable_new_entities", pref_disable_new_entities),
            ("pref_disable_polling", pref_disable_polling),
            ("title", title),
            ("version", version),
        ):
            if value is UNDEFINED or getattr(entry, attr) == value:
                continue

            _setter(entry, attr, value)
            changed = True

        if data is not UNDEFINED and entry.data != data:
            changed = True
            _setter(entry, "data", MappingProxyType(data))

        if options is not UNDEFINED and entry.options != options:
            changed = True
            _setter(entry, "options", MappingProxyType(options))

        if not changed:
            return False

        for listener in entry.update_listeners:
            self.hass.async_create_task(
                listener(self.hass, entry),
                f"config entry update listener {entry.title} {entry.domain} {entry.domain}",
            )

        self._async_schedule_save()
        entry.clear_cache()
        self._async_dispatch(ConfigEntryChange.UPDATED, entry)
        return True

    @callback
    def _async_dispatch(
        self, change_type: ConfigEntryChange, entry: ConfigEntry
    ) -> None:
        """Dispatch a config entry change."""
        async_dispatcher_send_internal(
            self.hass, SIGNAL_CONFIG_ENTRY_CHANGED, change_type, entry
        )

    async def async_forward_entry_setups(
        self, entry: ConfigEntry, platforms: Iterable[Platform | str]
    ) -> None:
        """Forward the setup of an entry to platforms.

        This method should be awaited before async_setup_entry is finished
        in each integration. This is to ensure that all platforms are loaded
        before the entry is set up. This ensures that the config entry cannot
        be unloaded before all platforms are loaded.

        This method is more efficient than async_forward_entry_setup as
        it can load multiple platforms at once and does not require a separate
        import executor job for each platform.
        """
        integration = await loader.async_get_integration(self.hass, entry.domain)
        if not integration.platforms_are_loaded(platforms):
            with async_pause_setup(self.hass, SetupPhases.WAIT_IMPORT_PLATFORMS):
                await integration.async_get_platforms(platforms)

        if not entry.setup_lock.locked():
            async with entry.setup_lock:
                if entry.state is not ConfigEntryState.LOADED:
                    raise OperationNotAllowed(
                        f"The config entry '{entry.title}' ({entry.domain}) with "
                        f"entry_id '{entry.entry_id}' cannot forward setup for "
                        f"{platforms} because it is in state {entry.state}, but needs "
                        f"to be in the {ConfigEntryState.LOADED} state"
                    )
                await self._async_forward_entry_setups_locked(entry, platforms)
        else:
            await self._async_forward_entry_setups_locked(entry, platforms)
            # If the lock was held when we stated, and it was released during
            # the platform setup, it means they did not await the setup call.
            if not entry.setup_lock.locked():
                _report_non_awaited_platform_forwards(
                    entry, "async_forward_entry_setups"
                )

    async def _async_forward_entry_setups_locked(
        self, entry: ConfigEntry, platforms: Iterable[Platform | str]
    ) -> None:
        await asyncio.gather(
            *(
                create_eager_task(
                    self._async_forward_entry_setup(entry, platform, False),
                    name=(
                        f"config entry forward setup {entry.title} "
                        f"{entry.domain} {entry.entry_id} {platform}"
                    ),
                    loop=self.hass.loop,
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

        This method is deprecated and will stop working in Home Assistant 2025.6.

        Instead, await async_forward_entry_setups as it can load
        multiple platforms at once and is more efficient since it
        does not require a separate import executor job for each platform.
        """
        report(
            "calls async_forward_entry_setup for "
            f"integration, {entry.domain} with title: {entry.title} "
            f"and entry_id: {entry.entry_id}, which is deprecated and "
            "will stop working in Home Assistant 2025.6, "
            "await async_forward_entry_setups instead",
            error_if_core=False,
            error_if_integration=False,
        )
        if not entry.setup_lock.locked():
            async with entry.setup_lock:
                if entry.state is not ConfigEntryState.LOADED:
                    raise OperationNotAllowed(
                        f"The config entry '{entry.title}' ({entry.domain}) with "
                        f"entry_id '{entry.entry_id}' cannot forward setup for "
                        f"{domain} because it is in state {entry.state}, but needs "
                        f"to be in the {ConfigEntryState.LOADED} state"
                    )
                return await self._async_forward_entry_setup(entry, domain, True)
        result = await self._async_forward_entry_setup(entry, domain, True)
        # If the lock was held when we stated, and it was released during
        # the platform setup, it means they did not await the setup call.
        if not entry.setup_lock.locked():
            _report_non_awaited_platform_forwards(entry, "async_forward_entry_setup")
        return result

    async def _async_forward_entry_setup(
        self,
        entry: ConfigEntry,
        domain: Platform | str,
        preload_platform: bool,
    ) -> bool:
        """Forward the setup of an entry to a different component."""
        # Setup Component if not set up yet
        if domain not in self.hass.config.components:
            with async_pause_setup(self.hass, SetupPhases.WAIT_BASE_PLATFORM_SETUP):
                result = await async_setup_component(
                    self.hass, domain, self._hass_config
                )

            if not result:
                return False

        if preload_platform:
            # If this is a late setup, we need to make sure the platform is loaded
            # so we do not end up waiting for when the EntityComponent calls
            # async_prepare_setup_platform
            integration = await loader.async_get_integration(self.hass, entry.domain)
            if not integration.platforms_are_loaded((domain,)):
                with async_pause_setup(self.hass, SetupPhases.WAIT_IMPORT_PLATFORMS):
                    await integration.async_get_platform(domain)

        integration = loader.async_get_loaded_integration(self.hass, domain)
        await entry.async_setup(self.hass, integration=integration)
        return True

    async def async_unload_platforms(
        self, entry: ConfigEntry, platforms: Iterable[Platform | str]
    ) -> bool:
        """Forward the unloading of an entry to platforms."""
        return all(
            await asyncio.gather(
                *(
                    create_eager_task(
                        self.async_forward_entry_unload(entry, platform),
                        name=(
                            f"config entry forward unload {entry.title} "
                            f"{entry.domain} {entry.entry_id} {platform}"
                        ),
                        loop=self.hass.loop,
                    )
                    for platform in platforms
                )
            )
        )

    async def async_forward_entry_unload(
        self, entry: ConfigEntry, domain: Platform | str
    ) -> bool:
        """Forward the unloading of an entry to a different component.

        Its is preferred to call async_unload_platforms instead
        of directly calling this method.
        """
        # It was never loaded.
        if domain not in self.hass.config.components:
            return True

        integration = loader.async_get_loaded_integration(self.hass, domain)

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
        setup_done = self.hass.data.get(DATA_SETUP_DONE, {})
        if setup_future := setup_done.get(entry.domain):
            await setup_future
        # The component was not loaded.
        if entry.domain not in self.hass.config.components:
            return False
        return entry.state is ConfigEntryState.LOADED


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


class ConfigEntryBaseFlow(data_entry_flow.FlowHandler[ConfigFlowResult]):
    """Base class for config and option flows."""

    _flow_result = ConfigFlowResult


class ConfigFlow(ConfigEntryBaseFlow):
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

        if not (
            entry := self.hass.config_entries.async_entry_for_domain_unique_id(
                self.handler, self.unique_id
            )
        ):
            return

        should_reload = False
        if (
            updates is not None
            and self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, **updates}
            )
            and reload_on_update
            and entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY)
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
            return
        if should_reload:
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
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

        return self.hass.config_entries.async_entry_for_domain_unique_id(
            self.handler, unique_id
        )

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
        return self.hass.config_entries.async_entries(
            self.handler,
            include_ignore or (include_ignore is None and self.source != SOURCE_USER),
        )

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
    ) -> list[ConfigFlowResult]:
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

    async def async_step_ignore(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Ignore this config flow."""
        await self.async_set_unique_id(user_input["unique_id"], raise_on_progress=False)
        return self.async_create_entry(title=user_input["title"], data={})

    async def async_step_unignore(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Rediscover a config entry by it's unique_id."""
        return self.async_abort(reason="not_implemented")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Handle a flow initialized by discovery."""
        await self._async_handle_discovery_without_unique_id()
        return await self.async_step_user()

    async def async_step_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle a flow initialized by discovery."""
        return await self._async_step_discovery_without_unique_id()

    @callback
    def async_abort(
        self,
        *,
        reason: str,
        description_placeholders: Mapping[str, str] | None = None,
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Handle a flow initialized by Bluetooth discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by DHCP discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by HASS IO discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle a flow initialized by integration specific discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by Homekit discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by MQTT discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by SSDP discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle a flow initialized by USB discovery."""
        return await self._async_step_discovery_without_unique_id()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Finish config flow and create a config entry."""
        result = super().async_create_entry(
            title=title,
            data=data,
            description=description,
            description_placeholders=description_placeholders,
        )

        result["minor_version"] = self.MINOR_VERSION
        result["options"] = options or {}
        result["version"] = self.VERSION

        return result

    @callback
    def async_update_reload_and_abort(
        self,
        entry: ConfigEntry,
        *,
        unique_id: str | None | UndefinedType = UNDEFINED,
        title: str | UndefinedType = UNDEFINED,
        data: Mapping[str, Any] | UndefinedType = UNDEFINED,
        options: Mapping[str, Any] | UndefinedType = UNDEFINED,
        reason: str = "reauth_successful",
        reload_even_if_entry_is_unchanged: bool = True,
    ) -> ConfigFlowResult:
        """Update config entry, reload config entry and finish config flow."""
        result = self.hass.config_entries.async_update_entry(
            entry=entry,
            unique_id=unique_id,
            title=title,
            data=data,
            options=options,
        )
        if reload_even_if_entry_is_unchanged or result:
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_abort(reason=reason)


class OptionsFlowManager(data_entry_flow.FlowManager[ConfigFlowResult]):
    """Flow to set options for a configuration entry."""

    _flow_result = ConfigFlowResult

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
        self,
        flow: data_entry_flow.FlowHandler[ConfigFlowResult],
        result: ConfigFlowResult,
    ) -> ConfigFlowResult:
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

    async def _async_setup_preview(
        self, flow: data_entry_flow.FlowHandler[ConfigFlowResult]
    ) -> None:
        """Set up preview for an option flow handler."""
        entry = self._async_get_config_entry(flow.handler)
        await _load_integration(self.hass, entry.domain, {})
        if entry.domain not in self._preview:
            self._preview.add(entry.domain)
            await flow.async_setup_preview(self.hass)


class OptionsFlow(ConfigEntryBaseFlow):
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

    @callback
    def _handle_entry_updated(
        self, event: Event[entity_registry.EventEntityRegistryUpdatedData]
    ) -> None:
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
            HassJob(self._async_handle_reload, cancel_on_shutdown=True),
        )

    @callback
    def _async_handle_reload(self, _now: Any) -> None:
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
        for entry_id in to_reload:
            self.hass.config_entries.async_schedule_reload(entry_id)


@callback
def _handle_entry_updated_filter(
    event_data: entity_registry.EventEntityRegistryUpdatedData,
) -> bool:
    """Handle entity registry entry update filter.

    Only handle changes to "disabled_by".
    If "disabled_by" was CONFIG_ENTRY, reload is not needed.
    """
    return not (
        event_data["action"] != "update"
        or "disabled_by" not in event_data["changes"]
        or event_data["changes"]["disabled_by"]
        is entity_registry.RegistryEntryDisabler.CONFIG_ENTRY
    )


async def support_entry_unload(hass: HomeAssistant, domain: str) -> bool:
    """Test if a domain supports entry unloading."""
    integration = await loader.async_get_integration(hass, domain)
    component = await integration.async_get_component()
    return hasattr(component, "async_unload_entry")


async def support_remove_from_device(hass: HomeAssistant, domain: str) -> bool:
    """Test if a domain supports being removed from a device."""
    integration = await loader.async_get_integration(hass, domain)
    component = await integration.async_get_component()
    return hasattr(component, "async_remove_config_entry_device")


async def _support_single_config_entry_only(hass: HomeAssistant, domain: str) -> bool:
    """Test if a domain supports only a single config entry."""
    integration = await loader.async_get_integration(hass, domain)
    return integration.single_config_entry


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
        await integration.async_get_platform("config_flow")
    except ImportError as err:
        _LOGGER.error(
            "Error occurred loading flow for integration %s: %s",
            domain,
            err,
        )
        raise data_entry_flow.UnknownHandler from err


async def _async_get_flow_handler(
    hass: HomeAssistant, domain: str, hass_config: ConfigType
) -> type[ConfigFlow]:
    """Get a flow handler for specified domain."""

    # First check if there is a handler registered for the domain
    if loader.is_component_module_loaded(hass, f"{domain}.config_flow") and (
        handler := HANDLERS.get(domain)
    ):
        return handler

    await _load_integration(hass, domain, hass_config)

    if handler := HANDLERS.get(domain):
        return handler

    raise data_entry_flow.UnknownHandler
