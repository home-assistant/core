"""Manage config entries in Home Assistant."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from contextvars import ContextVar
import functools
import logging
from types import MappingProxyType, MethodType
from typing import Any, Callable, Optional, cast
import weakref

import attr

from homeassistant import data_entry_flow, loader
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, CoreState, HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.event import Event
from homeassistant.helpers.typing import UNDEFINED, DiscoveryInfoType, UndefinedType
from homeassistant.setup import async_process_deps_reqs, async_setup_component
from homeassistant.util.decorator import Registry
import homeassistant.util.uuid as uuid_util

_LOGGER = logging.getLogger(__name__)

SOURCE_DISCOVERY = "discovery"
SOURCE_HASSIO = "hassio"
SOURCE_HOMEKIT = "homekit"
SOURCE_IMPORT = "import"
SOURCE_INTEGRATION_DISCOVERY = "integration_discovery"
SOURCE_MQTT = "mqtt"
SOURCE_SSDP = "ssdp"
SOURCE_USER = "user"
SOURCE_ZEROCONF = "zeroconf"
SOURCE_DHCP = "dhcp"

# If a user wants to hide a discovery from the UI they can "Ignore" it. The config_entries/ignore_flow
# websocket command creates a config entry with this source and while it exists normal discoveries
# with the same unique id are ignored.
SOURCE_IGNORE = "ignore"

# This is used when a user uses the "Stop Ignoring" button in the UI (the
# config_entries/ignore_flow websocket command). It's triggered after the "ignore" config entry has
# been removed and unloaded.
SOURCE_UNIGNORE = "unignore"

# This is used to signal that re-authentication is required by the user.
SOURCE_REAUTH = "reauth"

HANDLERS = Registry()

STORAGE_KEY = "core.config_entries"
STORAGE_VERSION = 1

# Deprecated since 0.73
PATH_CONFIG = ".config_entries.json"

SAVE_DELAY = 1

# The config entry has been set up successfully
ENTRY_STATE_LOADED = "loaded"
# There was an error while trying to set up this config entry
ENTRY_STATE_SETUP_ERROR = "setup_error"
# There was an error while trying to migrate the config entry to a new version
ENTRY_STATE_MIGRATION_ERROR = "migration_error"
# The config entry was not ready to be set up yet, but might be later
ENTRY_STATE_SETUP_RETRY = "setup_retry"
# The config entry has not been loaded
ENTRY_STATE_NOT_LOADED = "not_loaded"
# An error occurred when trying to unload the entry
ENTRY_STATE_FAILED_UNLOAD = "failed_unload"

UNRECOVERABLE_STATES = (ENTRY_STATE_MIGRATION_ERROR, ENTRY_STATE_FAILED_UNLOAD)

DEFAULT_DISCOVERY_UNIQUE_ID = "default_discovery_unique_id"
DISCOVERY_NOTIFICATION_ID = "config_entry_discovery"
DISCOVERY_SOURCES = (
    SOURCE_SSDP,
    SOURCE_ZEROCONF,
    SOURCE_DISCOVERY,
    SOURCE_IMPORT,
    SOURCE_UNIGNORE,
)

RECONFIGURE_NOTIFICATION_ID = "config_entry_reconfigure"

EVENT_FLOW_DISCOVERED = "config_entry_discovered"

DISABLED_USER = "user"

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


UpdateListenerType = Callable[[HomeAssistant, "ConfigEntry"], Any]


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
        "system_options",
        "source",
        "state",
        "disabled_by",
        "_setup_lock",
        "update_listeners",
        "reason",
        "_async_cancel_retry_setup",
        "_on_unload",
    )

    def __init__(
        self,
        version: int,
        domain: str,
        title: str,
        data: Mapping[str, Any],
        source: str,
        system_options: dict,
        options: Mapping[str, Any] | None = None,
        unique_id: str | None = None,
        entry_id: str | None = None,
        state: str = ENTRY_STATE_NOT_LOADED,
        disabled_by: str | None = None,
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
        self.system_options = SystemOptions(**system_options)

        # Source of the configuration (user, discovery, cloud)
        self.source = source

        # State of the entry (LOADED, NOT_LOADED)
        self.state = state

        # Unique ID of this entry.
        self.unique_id = unique_id

        # Config entry is disabled
        self.disabled_by = disabled_by

        # Supports unload
        self.supports_unload = False

        # Listeners to call on update
        self.update_listeners: list[
            weakref.ReferenceType[UpdateListenerType] | weakref.WeakMethod
        ] = []

        # Reason why config entry is in a failed state
        self.reason: str | None = None

        # Function to cancel a scheduled retry
        self._async_cancel_retry_setup: Callable[[], Any] | None = None

        # Hold list for functions to call on unload.
        self._on_unload: list[CALLBACK_TYPE] | None = None

    async def async_setup(
        self,
        hass: HomeAssistant,
        *,
        integration: loader.Integration | None = None,
        tries: int = 0,
    ) -> None:
        """Set up an entry."""
        current_entry.set(self)
        if self.source == SOURCE_IGNORE or self.disabled_by:
            return

        if integration is None:
            integration = await loader.async_get_integration(hass, self.domain)

        self.supports_unload = await support_entry_unload(hass, self.domain)

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
                self.state = ENTRY_STATE_SETUP_ERROR
                self.reason = "Import error"
            return

        if self.domain == integration.domain:
            try:
                integration.get_platform("config_flow")
            except ImportError as err:
                _LOGGER.error(
                    "Error importing platform config_flow from integration %s to set up %s configuration entry: %s",
                    integration.domain,
                    self.domain,
                    err,
                )
                self.state = ENTRY_STATE_SETUP_ERROR
                self.reason = "Import error"
                return

            # Perform migration
            if not await self.async_migrate(hass):
                self.state = ENTRY_STATE_MIGRATION_ERROR
                self.reason = None
                return

        error_reason = None

        try:
            result = await component.async_setup_entry(hass, self)  # type: ignore

            if not isinstance(result, bool):
                _LOGGER.error(
                    "%s.async_setup_entry did not return boolean", integration.domain
                )
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
            self._async_process_on_unload()
            self.async_start_reauth(hass)
            result = False
        except ConfigEntryNotReady as ex:
            self.state = ENTRY_STATE_SETUP_RETRY
            self.reason = str(ex) or None
            wait_time = 2 ** min(tries, 4) * 5
            tries += 1
            message = str(ex)
            ready_message = f"ready yet: {message}" if message else "ready yet"
            if tries == 1:
                _LOGGER.warning(
                    "Config entry '%s' for %s integration not %s; Retrying in background",
                    self.title,
                    self.domain,
                    ready_message,
                )
            else:
                _LOGGER.debug(
                    "Config entry '%s' for %s integration not %s; Retrying in %d seconds",
                    self.title,
                    self.domain,
                    ready_message,
                    wait_time,
                )

            async def setup_again(*_: Any) -> None:
                """Run setup again."""
                self._async_cancel_retry_setup = None
                await self.async_setup(hass, integration=integration, tries=tries)

            if hass.state == CoreState.running:
                self._async_cancel_retry_setup = hass.helpers.event.async_call_later(
                    wait_time, setup_again
                )
            else:
                self._async_cancel_retry_setup = hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED, setup_again
                )

            self._async_process_on_unload()
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error setting up entry %s for %s", self.title, integration.domain
            )
            result = False

        # Only store setup result as state if it was not forwarded.
        if self.domain != integration.domain:
            return

        if result:
            self.state = ENTRY_STATE_LOADED
            self.reason = None
        else:
            self.state = ENTRY_STATE_SETUP_ERROR
            self.reason = error_reason

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
            self.state = ENTRY_STATE_NOT_LOADED
            self.reason = None
            return True

        if integration is None:
            try:
                integration = await loader.async_get_integration(hass, self.domain)
            except loader.IntegrationNotFound:
                # The integration was likely a custom_component
                # that was uninstalled, or an integration
                # that has been renamed without removing the config
                # entry.
                self.state = ENTRY_STATE_NOT_LOADED
                self.reason = None
                return True

        component = integration.get_component()

        if integration.domain == self.domain:
            if self.state in UNRECOVERABLE_STATES:
                return False

            if self.state != ENTRY_STATE_LOADED:
                self.async_cancel_retry_setup()

                self.state = ENTRY_STATE_NOT_LOADED
                self.reason = None
                return True

        supports_unload = hasattr(component, "async_unload_entry")

        if not supports_unload:
            if integration.domain == self.domain:
                self.state = ENTRY_STATE_FAILED_UNLOAD
                self.reason = "Unload not supported"
            return False

        try:
            result = await component.async_unload_entry(hass, self)  # type: ignore

            assert isinstance(result, bool)

            # Only adjust state if we unloaded the component
            if result and integration.domain == self.domain:
                self.state = ENTRY_STATE_NOT_LOADED
                self.reason = None

            self._async_process_on_unload()

            return result
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error unloading entry %s for %s", self.title, integration.domain
            )
            if integration.domain == self.domain:
                self.state = ENTRY_STATE_FAILED_UNLOAD
                self.reason = "Unknown error"
            return False

    async def async_remove(self, hass: HomeAssistant) -> None:
        """Invoke remove callback on component."""
        if self.source == SOURCE_IGNORE:
            return

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
            await component.async_remove_entry(hass, self)  # type: ignore
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error calling entry remove callback %s for %s",
                self.title,
                integration.domain,
            )

    async def async_migrate(self, hass: HomeAssistant) -> bool:
        """Migrate an entry.

        Returns True if config entry is up-to-date or has been migrated.
        """
        handler = HANDLERS.get(self.domain)
        if handler is None:
            _LOGGER.error(
                "Flow handler not found for entry %s for %s", self.title, self.domain
            )
            return False
        # Handler may be a partial
        while isinstance(handler, functools.partial):
            handler = handler.func

        if self.version == handler.VERSION:
            return True

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
            result = await component.async_migrate_entry(hass, self)  # type: ignore
            if not isinstance(result, bool):
                _LOGGER.error(
                    "%s.async_migrate_entry did not return boolean", self.domain
                )
                return False
            if result:
                # pylint: disable=protected-access
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
        weak_listener: Any
        # weakref.ref is not applicable to a bound method, e.g. method of a class instance, as reference will die immediately
        if hasattr(listener, "__self__"):
            weak_listener = weakref.WeakMethod(cast(MethodType, listener))
        else:
            weak_listener = weakref.ref(listener)
        self.update_listeners.append(weak_listener)

        return lambda: self.update_listeners.remove(weak_listener)

    def as_dict(self) -> dict[str, Any]:
        """Return dictionary version of this entry."""
        return {
            "entry_id": self.entry_id,
            "version": self.version,
            "domain": self.domain,
            "title": self.title,
            "data": dict(self.data),
            "options": dict(self.options),
            "system_options": self.system_options.as_dict(),
            "source": self.source,
            "unique_id": self.unique_id,
            "disabled_by": self.disabled_by,
        }

    @callback
    def async_on_unload(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when config entry is unloaded."""
        if self._on_unload is None:
            self._on_unload = []
        self._on_unload.append(func)

    @callback
    def _async_process_on_unload(self) -> None:
        """Process the on_unload callbacks."""
        if self._on_unload is not None:
            while self._on_unload:
                self._on_unload.pop()()

    @callback
    def async_start_reauth(self, hass: HomeAssistant) -> None:
        """Start a reauth flow."""
        flow_context = {
            "source": SOURCE_REAUTH,
            "entry_id": self.entry_id,
            "unique_id": self.unique_id,
        }

        for flow in hass.config_entries.flow.async_progress():
            if flow["context"] == flow_context:
                return

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                self.domain,
                context=flow_context,
                data=self.data,
            )
        )


current_entry: ContextVar[ConfigEntry | None] = ContextVar(
    "current_entry", default=None
)


class ConfigEntriesFlowManager(data_entry_flow.FlowManager):
    """Manage all the config entry flows that are in progress."""

    def __init__(
        self, hass: HomeAssistant, config_entries: ConfigEntries, hass_config: dict
    ):
        """Initialize the config entry flow manager."""
        super().__init__(hass)
        self.config_entries = config_entries
        self._hass_config = hass_config

    async def async_finish_flow(
        self, flow: data_entry_flow.FlowHandler, result: data_entry_flow.FlowResult
    ) -> data_entry_flow.FlowResult:
        """Finish a config flow and add an entry."""
        flow = cast(ConfigFlow, flow)

        # Remove notification if no other discovery config entries in progress
        if not any(
            ent["context"]["source"] in DISCOVERY_SOURCES
            for ent in self.hass.config_entries.flow.async_progress()
            if ent["flow_id"] != flow.flow_id
        ):
            self.hass.components.persistent_notification.async_dismiss(
                DISCOVERY_NOTIFICATION_ID
            )

        if result["type"] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            return result

        # Check if config entry exists with unique ID. Unload it.
        existing_entry = None

        if flow.unique_id is not None:
            # Abort all flows in progress with same unique ID.
            for progress_flow in self.async_progress():
                if (
                    progress_flow["handler"] == flow.handler
                    and progress_flow["flow_id"] != flow.flow_id
                    and progress_flow["context"].get("unique_id") == flow.unique_id
                ):
                    self.async_abort(progress_flow["flow_id"])

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
        if (
            existing_entry is not None
            and existing_entry.state not in UNRECOVERABLE_STATES
        ):
            await self.config_entries.async_unload(existing_entry.entry_id)

        entry = ConfigEntry(
            version=result["version"],
            domain=result["handler"],
            title=result["title"],
            data=result["data"],
            options=result["options"],
            system_options={},
            source=flow.context["source"],
            unique_id=flow.unique_id,
        )

        await self.config_entries.async_add(entry)

        if existing_entry is not None:
            await self.config_entries.async_remove(existing_entry.entry_id)

        result["result"] = entry
        return result

    async def async_create_flow(
        self, handler_key: Any, *, context: dict | None = None, data: Any = None
    ) -> ConfigFlow:
        """Create a flow for specified handler.

        Handler key is the domain of the component that we want to set up.
        """
        try:
            integration = await loader.async_get_integration(self.hass, handler_key)
        except loader.IntegrationNotFound as err:
            _LOGGER.error("Cannot find integration %s", handler_key)
            raise data_entry_flow.UnknownHandler from err

        # Make sure requirements and dependencies of component are resolved
        await async_process_deps_reqs(self.hass, self._hass_config, integration)

        try:
            integration.get_platform("config_flow")
        except ImportError as err:
            _LOGGER.error(
                "Error occurred loading configuration flow for integration %s: %s",
                handler_key,
                err,
            )
            raise data_entry_flow.UnknownHandler

        handler = HANDLERS.get(handler_key)

        if handler is None:
            raise data_entry_flow.UnknownHandler

        if not context or "source" not in context:
            raise KeyError("Context not set or doesn't have a source set")

        flow = cast(ConfigFlow, handler())
        flow.init_step = context["source"]
        return flow

    async def async_post_init(
        self, flow: data_entry_flow.FlowHandler, result: data_entry_flow.FlowResult
    ) -> None:
        """After a flow is initialised trigger new flow notifications."""
        source = flow.context["source"]

        # Create notification.
        if source in DISCOVERY_SOURCES:
            self.hass.bus.async_fire(EVENT_FLOW_DISCOVERED)
            self.hass.components.persistent_notification.async_create(
                title="New devices discovered",
                message=(
                    "We have discovered new devices on your network. "
                    "[Check it out](/config/integrations)."
                ),
                notification_id=DISCOVERY_NOTIFICATION_ID,
            )
        elif source == SOURCE_REAUTH:
            self.hass.components.persistent_notification.async_create(
                title="Integration requires reconfiguration",
                message=(
                    "At least one of your integrations requires reconfiguration to "
                    "continue functioning. [Check it out](/config/integrations)."
                ),
                notification_id=RECONFIGURE_NOTIFICATION_ID,
            )


class ConfigEntries:
    """Manage the configuration entries.

    An instance of this object is available via `hass.config_entries`.
    """

    def __init__(self, hass: HomeAssistant, hass_config: dict) -> None:
        """Initialize the entry manager."""
        self.hass = hass
        self.flow = ConfigEntriesFlowManager(hass, self, hass_config)
        self.options = OptionsFlowManager(hass)
        self._hass_config = hass_config
        self._entries: dict[str, ConfigEntry] = {}
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
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
        return [entry for entry in self._entries.values() if entry.domain == domain]

    async def async_add(self, entry: ConfigEntry) -> None:
        """Add and setup an entry."""
        if entry.entry_id in self._entries:
            raise HomeAssistantError(
                f"An entry with the id {entry.entry_id} already exists."
            )
        self._entries[entry.entry_id] = entry
        await self.async_setup(entry.entry_id)
        self._async_schedule_save()

    async def async_remove(self, entry_id: str) -> dict[str, Any]:
        """Remove an entry."""
        entry = self.async_get_entry(entry_id)

        if entry is None:
            raise UnknownEntry

        if entry.state in UNRECOVERABLE_STATES:
            unload_success = entry.state != ENTRY_STATE_FAILED_UNLOAD
        else:
            unload_success = await self.async_unload(entry_id)

        await entry.async_remove(self.hass)

        del self._entries[entry.entry_id]
        self._async_schedule_save()

        dev_reg, ent_reg = await asyncio.gather(
            self.hass.helpers.device_registry.async_get_registry(),
            self.hass.helpers.entity_registry.async_get_registry(),
        )

        dev_reg.async_clear_config_entry(entry_id)
        ent_reg.async_clear_config_entry(entry_id)

        # After we have fully removed an "ignore" config entry we can try and rediscover it so that a
        # user is able to immediately start configuring it. We do this by starting a new flow with
        # the 'unignore' step. If the integration doesn't implement async_step_unignore then
        # this will be a no-op.
        if entry.source == SOURCE_IGNORE:
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    entry.domain,
                    context={"source": SOURCE_UNIGNORE},
                    data={"unique_id": entry.unique_id},
                )
            )

        return {"require_restart": not unload_success}

    async def _async_shutdown(self, event: Event) -> None:
        """Call when Home Assistant is stopping."""
        await asyncio.gather(
            *[entry.async_shutdown() for entry in self._entries.values()]
        )
        await self.flow.async_shutdown()

    async def async_initialize(self) -> None:
        """Initialize config entry config."""
        # Migrating for config entries stored before 0.73
        config = await self.hass.helpers.storage.async_migrator(
            self.hass.config.path(PATH_CONFIG),
            self._store,
            old_conf_migrate_func=_old_conf_migrator,
        )

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_shutdown)

        if config is None:
            self._entries = {}
            return

        self._entries = {
            entry["entry_id"]: ConfigEntry(
                version=entry["version"],
                domain=entry["domain"],
                entry_id=entry["entry_id"],
                data=entry["data"],
                source=entry["source"],
                title=entry["title"],
                # New in 0.89
                options=entry.get("options"),
                # New in 0.98
                system_options=entry.get("system_options", {}),
                # New in 0.104
                unique_id=entry.get("unique_id"),
                # New in 2021.3
                disabled_by=entry.get("disabled_by"),
            )
            for entry in config["entries"]
        }

    async def async_setup(self, entry_id: str) -> bool:
        """Set up a config entry.

        Return True if entry has been successfully loaded.
        """
        entry = self.async_get_entry(entry_id)

        if entry is None:
            raise UnknownEntry

        if entry.state != ENTRY_STATE_NOT_LOADED:
            raise OperationNotAllowed

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

        return entry.state == ENTRY_STATE_LOADED

    async def async_unload(self, entry_id: str) -> bool:
        """Unload a config entry."""
        entry = self.async_get_entry(entry_id)

        if entry is None:
            raise UnknownEntry

        if entry.state in UNRECOVERABLE_STATES:
            raise OperationNotAllowed

        return await entry.async_unload(self.hass)

    async def async_reload(self, entry_id: str) -> bool:
        """Reload an entry.

        If an entry was not loaded, will just load.
        """
        entry = self.async_get_entry(entry_id)

        if entry is None:
            raise UnknownEntry

        unload_result = await self.async_unload(entry_id)

        if not unload_result or entry.disabled_by:
            return unload_result

        return await self.async_setup(entry_id)

    async def async_set_disabled_by(
        self, entry_id: str, disabled_by: str | None
    ) -> bool:
        """Disable an entry.

        If disabled_by is changed, the config entry will be reloaded.
        """
        entry = self.async_get_entry(entry_id)

        if entry is None:
            raise UnknownEntry

        if entry.disabled_by == disabled_by:
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
        unique_id: str | dict | None | UndefinedType = UNDEFINED,
        title: str | dict | UndefinedType = UNDEFINED,
        data: dict | UndefinedType = UNDEFINED,
        options: Mapping[str, Any] | UndefinedType = UNDEFINED,
        system_options: dict | UndefinedType = UNDEFINED,
    ) -> bool:
        """Update a config entry.

        If the entry was changed, the update_listeners are
        fired and this function returns True

        If the entry was not changed, the update_listeners are
        not fired and this function returns False
        """
        changed = False

        if unique_id is not UNDEFINED and entry.unique_id != unique_id:
            changed = True
            entry.unique_id = cast(Optional[str], unique_id)

        if title is not UNDEFINED and entry.title != title:
            changed = True
            entry.title = cast(str, title)

        if data is not UNDEFINED and entry.data != data:  # type: ignore
            changed = True
            entry.data = MappingProxyType(data)

        if options is not UNDEFINED and entry.options != options:
            changed = True
            entry.options = MappingProxyType(options)

        if (
            system_options is not UNDEFINED
            and entry.system_options.as_dict() != system_options
        ):
            changed = True
            entry.system_options.update(**system_options)

        if not changed:
            return False

        for listener_ref in entry.update_listeners:
            listener = listener_ref()
            if listener is not None:
                self.hass.async_create_task(listener(self.hass, entry))

        self._async_schedule_save()

        return True

    @callback
    def async_setup_platforms(
        self, entry: ConfigEntry, platforms: Iterable[str]
    ) -> None:
        """Forward the setup of an entry to platforms."""
        for platform in platforms:
            self.hass.async_create_task(self.async_forward_entry_setup(entry, platform))

    async def async_forward_entry_setup(self, entry: ConfigEntry, domain: str) -> bool:
        """Forward the setup of an entry to a different component.

        By default an entry is setup with the component it belongs to. If that
        component also has related platforms, the component will have to
        forward the entry to be setup by that component.

        You don't want to await this coroutine if it is called as part of the
        setup of a component, because it can cause a deadlock.
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
        self, entry: ConfigEntry, platforms: Iterable[str]
    ) -> bool:
        """Forward the unloading of an entry to platforms."""
        return all(
            await asyncio.gather(
                *[
                    self.async_forward_entry_unload(entry, platform)
                    for platform in platforms
                ]
            )
        )

    async def async_forward_entry_unload(self, entry: ConfigEntry, domain: str) -> bool:
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


async def _old_conf_migrator(old_config: dict[str, Any]) -> dict[str, Any]:
    """Migrate the pre-0.73 config format to the latest version."""
    return {"entries": old_config}


class ConfigFlow(data_entry_flow.FlowHandler):
    """Base class for config flows with some helpers."""

    def __init_subclass__(cls, domain: str | None = None, **kwargs: Any) -> None:
        """Initialize a subclass, register if possible."""
        super().__init_subclass__(**kwargs)  # type: ignore
        if domain is not None:
            HANDLERS.register(domain)(cls)

    @property
    def unique_id(self) -> str | None:
        """Return unique ID if available."""
        if not self.context:
            return None

        return cast(Optional[str], self.context.get("unique_id"))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        raise data_entry_flow.UnknownHandler

    @callback
    def _abort_if_unique_id_configured(
        self,
        updates: dict[Any, Any] | None = None,
        reload_on_update: bool = True,
    ) -> None:
        """Abort if the unique ID is already configured."""
        if self.unique_id is None:
            return

        for entry in self._async_current_entries(include_ignore=True):
            if entry.unique_id == self.unique_id:
                if updates is not None:
                    changed = self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, **updates}
                    )
                    if (
                        changed
                        and reload_on_update
                        and entry.state in (ENTRY_STATE_LOADED, ENTRY_STATE_SETUP_RETRY)
                    ):
                        self.hass.async_create_task(
                            self.hass.config_entries.async_reload(entry.entry_id)
                        )
                # Allow ignored entries to be configured on manual user step
                if entry.source == SOURCE_IGNORE and self.source == SOURCE_USER:
                    continue
                raise data_entry_flow.AbortFlow("already_configured")

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
            for progress in self._async_in_progress():
                if progress["context"].get("unique_id") == unique_id:
                    raise data_entry_flow.AbortFlow("already_in_progress")

        self.context["unique_id"] = unique_id

        # Abort discoveries done using the default discovery unique id
        if unique_id != DEFAULT_DISCOVERY_UNIQUE_ID:
            for progress in self._async_in_progress():
                if progress["context"].get("unique_id") == DEFAULT_DISCOVERY_UNIQUE_ID:
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

        If the flow is user initiated, filter out ignored entries unless include_ignore is True.
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
        self, include_uninitialized: bool = False
    ) -> list[data_entry_flow.FlowResult]:
        """Return other in progress flows for current domain."""
        return [
            flw
            for flw in self.hass.config_entries.flow.async_progress(
                include_uninitialized=include_uninitialized
            )
            if flw["handler"] == self.handler and flw["flow_id"] != self.flow_id
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

    async def async_step_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by discovery."""
        await self._async_handle_discovery_without_unique_id()
        return await self.async_step_user()

    @callback
    def async_abort(
        self, *, reason: str, description_placeholders: dict | None = None
    ) -> data_entry_flow.FlowResult:
        """Abort the config flow."""
        # Remove reauth notification if no reauth flows are in progress
        if self.source == SOURCE_REAUTH and not any(
            ent["context"]["source"] == SOURCE_REAUTH
            for ent in self.hass.config_entries.flow.async_progress()
            if ent["flow_id"] != self.flow_id
        ):
            self.hass.components.persistent_notification.async_dismiss(
                RECONFIGURE_NOTIFICATION_ID
            )

        return super().async_abort(
            reason=reason, description_placeholders=description_placeholders
        )

    async def async_step_hassio(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by HASS IO discovery."""
        return await self.async_step_discovery(discovery_info)

    async def async_step_homekit(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by Homekit discovery."""
        return await self.async_step_discovery(discovery_info)

    async def async_step_mqtt(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by MQTT discovery."""
        return await self.async_step_discovery(discovery_info)

    async def async_step_ssdp(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by SSDP discovery."""
        return await self.async_step_discovery(discovery_info)

    async def async_step_zeroconf(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by Zeroconf discovery."""
        return await self.async_step_discovery(discovery_info)

    async def async_step_dhcp(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Handle a flow initialized by DHCP discovery."""
        return await self.async_step_discovery(discovery_info)

    @callback
    def async_create_entry(  # pylint: disable=arguments-differ
        self,
        *,
        title: str,
        data: Mapping[str, Any],
        description: str | None = None,
        description_placeholders: dict | None = None,
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

    async def async_create_flow(
        self,
        handler_key: Any,
        *,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> OptionsFlow:
        """Create an options flow for a config entry.

        Entry_id and flow.handler is the same thing to map entry with flow.
        """
        entry = self.hass.config_entries.async_get_entry(handler_key)
        if entry is None:
            raise UnknownEntry(handler_key)

        if entry.domain not in HANDLERS:
            raise data_entry_flow.UnknownHandler

        return cast(OptionsFlow, HANDLERS[entry.domain].async_get_options_flow(entry))

    async def async_finish_flow(
        self, flow: data_entry_flow.FlowHandler, result: data_entry_flow.FlowResult
    ) -> data_entry_flow.FlowResult:
        """Finish an options flow and update options for configuration entry.

        Flow.handler and entry_id is the same thing to map flow with entry.
        """
        flow = cast(OptionsFlow, flow)

        if result["type"] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            return result

        entry = self.hass.config_entries.async_get_entry(flow.handler)
        if entry is None:
            raise UnknownEntry(flow.handler)
        if result["data"] is not None:
            self.hass.config_entries.async_update_entry(entry, options=result["data"])

        result["result"] = True
        return result


class OptionsFlow(data_entry_flow.FlowHandler):
    """Base class for config option flows."""

    handler: str


@attr.s(slots=True)
class SystemOptions:
    """Config entry system options."""

    disable_new_entities: bool = attr.ib(default=False)

    def update(self, *, disable_new_entities: bool) -> None:
        """Update properties."""
        self.disable_new_entities = disable_new_entities

    def as_dict(self) -> dict[str, Any]:
        """Return dictionary version of this config entries system options."""
        return {"disable_new_entities": self.disable_new_entities}


class EntityRegistryDisabledHandler:
    """Handler to handle when entities related to config entries updating disabled_by."""

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
            self.registry = await entity_registry.async_get_registry(self.hass)

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

        self._remove_call_later = self.hass.helpers.event.async_call_later(
            RELOAD_AFTER_UPDATE_DELAY, self._handle_reload
        )

    async def _handle_reload(self, _now: Any) -> None:
        """Handle a reload."""
        self._remove_call_later = None
        to_reload = self.changed
        self.changed = set()

        _LOGGER.info(
            "Reloading configuration entries because disabled_by changed in entity registry: %s",
            ", ".join(self.changed),
        )

        await asyncio.gather(
            *[self.hass.config_entries.async_reload(entry_id) for entry_id in to_reload]
        )


@callback
def _handle_entry_updated_filter(event: Event) -> bool:
    """Handle entity registry entry update filter.

    Only handle changes to "disabled_by".
    If "disabled_by" was DISABLED_CONFIG_ENTRY, reload is not needed.
    """
    if (
        event.data["action"] != "update"
        or "disabled_by" not in event.data["changes"]
        or event.data["changes"]["disabled_by"] == entity_registry.DISABLED_CONFIG_ENTRY
    ):
        return False
    return True


async def support_entry_unload(hass: HomeAssistant, domain: str) -> bool:
    """Test if a domain supports entry unloading."""
    integration = await loader.async_get_integration(hass, domain)
    component = integration.get_component()
    return hasattr(component, "async_unload_entry")
