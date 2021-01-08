"""Manage config entries in Home Assistant."""
import asyncio
import logging
import functools
import uuid
from typing import (
    Any,
    Callable,
    List,
    Optional,
    Set,  # noqa pylint: disable=unused-import
)
import weakref

from homeassistant import data_entry_flow, loader
from homeassistant.core import callback, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ConfigEntryNotReady
from homeassistant.setup import async_setup_component, async_process_deps_reqs
from homeassistant.util.decorator import Registry


# mypy: allow-untyped-defs

_LOGGER = logging.getLogger(__name__)
_UNDEF = object()

SOURCE_USER = "user"
SOURCE_DISCOVERY = "discovery"
SOURCE_IMPORT = "import"

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

DISCOVERY_NOTIFICATION_ID = "config_entry_discovery"
DISCOVERY_SOURCES = ("ssdp", "zeroconf", SOURCE_DISCOVERY, SOURCE_IMPORT)

EVENT_FLOW_DISCOVERED = "config_entry_discovered"

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


class ConfigEntry:
    """Hold a configuration entry."""

    __slots__ = (
        "entry_id",
        "version",
        "domain",
        "title",
        "data",
        "options",
        "source",
        "connection_class",
        "state",
        "_setup_lock",
        "update_listeners",
        "_async_cancel_retry_setup",
    )

    def __init__(
        self,
        version: int,
        domain: str,
        title: str,
        data: dict,
        source: str,
        connection_class: str,
        options: Optional[dict] = None,
        entry_id: Optional[str] = None,
        state: str = ENTRY_STATE_NOT_LOADED,
    ) -> None:
        """Initialize a config entry."""
        # Unique id of the config entry
        self.entry_id = entry_id or uuid.uuid4().hex

        # Version of the configuration.
        self.version = version

        # Domain the configuration belongs to
        self.domain = domain

        # Title of the configuration
        self.title = title

        # Config data
        self.data = data

        # Entry options
        self.options = options or {}

        # Source of the configuration (user, discovery, cloud)
        self.source = source

        # Connection class
        self.connection_class = connection_class

        # State of the entry (LOADED, NOT_LOADED)
        self.state = state

        # Listeners to call on update
        self.update_listeners = []  # type: list

        # Function to cancel a scheduled retry
        self._async_cancel_retry_setup = None  # type: Optional[Callable[[], Any]]

    async def async_setup(
        self,
        hass: HomeAssistant,
        *,
        integration: Optional[loader.Integration] = None,
        tries: int = 0,
    ) -> None:
        """Set up an entry."""
        if integration is None:
            integration = await loader.async_get_integration(hass, self.domain)

        try:
            component = integration.get_component()
            if self.domain == integration.domain:
                integration.get_platform("config_flow")
        except ImportError as err:
            _LOGGER.error(
                "Error importing integration %s to set up %s config entry: %s",
                integration.domain,
                self.domain,
                err,
            )
            if self.domain == integration.domain:
                self.state = ENTRY_STATE_SETUP_ERROR
            return

        # Perform migration
        if integration.domain == self.domain:
            if not await self.async_migrate(hass):
                self.state = ENTRY_STATE_MIGRATION_ERROR
                return

        try:
            result = await component.async_setup_entry(  # type: ignore
                hass, self
            )

            if not isinstance(result, bool):
                _LOGGER.error(
                    "%s.async_setup_entry did not return boolean", integration.domain
                )
                result = False
        except ConfigEntryNotReady:
            self.state = ENTRY_STATE_SETUP_RETRY
            wait_time = 2 ** min(tries, 4) * 5
            tries += 1
            _LOGGER.warning(
                "Config entry for %s not ready yet. Retrying in %d seconds.",
                self.domain,
                wait_time,
            )

            async def setup_again(now):
                """Run setup again."""
                self._async_cancel_retry_setup = None
                await self.async_setup(hass, integration=integration, tries=tries)

            self._async_cancel_retry_setup = hass.helpers.event.async_call_later(
                wait_time, setup_again
            )
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
        else:
            self.state = ENTRY_STATE_SETUP_ERROR

    async def async_unload(
        self, hass: HomeAssistant, *, integration: Optional[loader.Integration] = None
    ) -> bool:
        """Unload an entry.

        Returns if unload is possible and was successful.
        """
        if integration is None:
            integration = await loader.async_get_integration(hass, self.domain)

        component = integration.get_component()

        if integration.domain == self.domain:
            if self.state in UNRECOVERABLE_STATES:
                return False

            if self.state != ENTRY_STATE_LOADED:
                if self._async_cancel_retry_setup is not None:
                    self._async_cancel_retry_setup()
                    self._async_cancel_retry_setup = None

                self.state = ENTRY_STATE_NOT_LOADED
                return True

        supports_unload = hasattr(component, "async_unload_entry")

        if not supports_unload:
            if integration.domain == self.domain:
                self.state = ENTRY_STATE_FAILED_UNLOAD
            return False

        try:
            result = await component.async_unload_entry(  # type: ignore
                hass, self
            )

            assert isinstance(result, bool)

            # Only adjust state if we unloaded the component
            if result and integration.domain == self.domain:
                self.state = ENTRY_STATE_NOT_LOADED

            return result
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error unloading entry %s for %s", self.title, integration.domain
            )
            if integration.domain == self.domain:
                self.state = ENTRY_STATE_FAILED_UNLOAD
            return False

    async def async_remove(self, hass: HomeAssistant) -> None:
        """Invoke remove callback on component."""
        integration = await loader.async_get_integration(hass, self.domain)
        component = integration.get_component()
        if not hasattr(component, "async_remove_entry"):
            return
        try:
            await component.async_remove_entry(  # type: ignore
                hass, self
            )
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
            result = await component.async_migrate_entry(  # type: ignore
                hass, self
            )
            if not isinstance(result, bool):
                _LOGGER.error(
                    "%s.async_migrate_entry did not return boolean", self.domain
                )
                return False
            if result:
                # pylint: disable=protected-access
                hass.config_entries._async_schedule_save()  # type: ignore
            return result
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Error migrating entry %s for %s", self.title, self.domain
            )
            return False

    def add_update_listener(self, listener: Callable) -> Callable:
        """Listen for when entry is updated.

        Listener: Callback function(hass, entry)

        Returns function to unlisten.
        """
        weak_listener = weakref.ref(listener)
        self.update_listeners.append(weak_listener)

        return lambda: self.update_listeners.remove(weak_listener)

    def as_dict(self):
        """Return dictionary version of this entry."""
        return {
            "entry_id": self.entry_id,
            "version": self.version,
            "domain": self.domain,
            "title": self.title,
            "data": self.data,
            "options": self.options,
            "source": self.source,
            "connection_class": self.connection_class,
        }


class ConfigEntries:
    """Manage the configuration entries.

    An instance of this object is available via `hass.config_entries`.
    """

    def __init__(self, hass: HomeAssistant, hass_config: dict) -> None:
        """Initialize the entry manager."""
        self.hass = hass
        self.flow = data_entry_flow.FlowManager(
            hass, self._async_create_flow, self._async_finish_flow
        )
        self.options = OptionsFlowManager(hass)
        self._hass_config = hass_config
        self._entries = []  # type: List[ConfigEntry]
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_domains(self) -> List[str]:
        """Return domains for which we have entries."""
        seen = set()  # type: Set[str]
        result = []

        for entry in self._entries:
            if entry.domain not in seen:
                seen.add(entry.domain)
                result.append(entry.domain)

        return result

    @callback
    def async_get_entry(self, entry_id: str) -> Optional[ConfigEntry]:
        """Return entry with matching entry_id."""
        for entry in self._entries:
            if entry_id == entry.entry_id:
                return entry
        return None

    @callback
    def async_entries(self, domain: Optional[str] = None) -> List[ConfigEntry]:
        """Return all entries or entries for a specific domain."""
        if domain is None:
            return list(self._entries)
        return [entry for entry in self._entries if entry.domain == domain]

    async def async_remove(self, entry_id):
        """Remove an entry."""
        entry = self.async_get_entry(entry_id)

        if entry is None:
            raise UnknownEntry

        if entry.state in UNRECOVERABLE_STATES:
            unload_success = entry.state != ENTRY_STATE_FAILED_UNLOAD
        else:
            unload_success = await self.async_unload(entry_id)

        await entry.async_remove(self.hass)

        self._entries.remove(entry)
        self._async_schedule_save()

        dev_reg, ent_reg = await asyncio.gather(
            self.hass.helpers.device_registry.async_get_registry(),
            self.hass.helpers.entity_registry.async_get_registry(),
        )

        dev_reg.async_clear_config_entry(entry_id)
        ent_reg.async_clear_config_entry(entry_id)

        return {"require_restart": not unload_success}

    async def async_initialize(self) -> None:
        """Initialize config entry config."""
        # Migrating for config entries stored before 0.73
        config = await self.hass.helpers.storage.async_migrator(
            self.hass.config.path(PATH_CONFIG),
            self._store,
            old_conf_migrate_func=_old_conf_migrator,
        )

        if config is None:
            self._entries = []
            return

        self._entries = [
            ConfigEntry(
                version=entry["version"],
                domain=entry["domain"],
                entry_id=entry["entry_id"],
                data=entry["data"],
                source=entry["source"],
                title=entry["title"],
                # New in 0.79
                connection_class=entry.get("connection_class", CONN_CLASS_UNKNOWN),
                # New in 0.89
                options=entry.get("options"),
            )
            for entry in config["entries"]
        ]

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
        unload_result = await self.async_unload(entry_id)

        if not unload_result:
            return unload_result

        return await self.async_setup(entry_id)

    @callback
    def async_update_entry(self, entry, *, data=_UNDEF, options=_UNDEF):
        """Update a config entry."""
        if data is not _UNDEF:
            entry.data = data

        if options is not _UNDEF:
            entry.options = options

        if data is not _UNDEF or options is not _UNDEF:
            for listener_ref in entry.update_listeners:
                listener = listener_ref()
                self.hass.async_create_task(listener(self.hass, entry))

        self._async_schedule_save()

    async def async_forward_entry_setup(self, entry, domain):
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

    async def async_forward_entry_unload(self, entry, domain):
        """Forward the unloading of an entry to a different component."""
        # It was never loaded.
        if domain not in self.hass.config.components:
            return True

        integration = await loader.async_get_integration(self.hass, domain)

        return await entry.async_unload(self.hass, integration=integration)

    async def _async_finish_flow(self, flow, result):
        """Finish a config flow and add an entry."""
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

        entry = ConfigEntry(
            version=result["version"],
            domain=result["handler"],
            title=result["title"],
            data=result["data"],
            options={},
            source=flow.context["source"],
            connection_class=flow.CONNECTION_CLASS,
        )
        self._entries.append(entry)
        self._async_schedule_save()

        await self.async_setup(entry.entry_id)

        result["result"] = entry
        return result

    async def _async_create_flow(self, handler_key, *, context, data):
        """Create a flow for specified handler.

        Handler key is the domain of the component that we want to set up.
        """
        try:
            integration = await loader.async_get_integration(self.hass, handler_key)
        except loader.IntegrationNotFound:
            _LOGGER.error("Cannot find integration %s", handler_key)
            raise data_entry_flow.UnknownHandler

        # Make sure requirements and dependencies of component are resolved
        await async_process_deps_reqs(self.hass, self._hass_config, integration)

        try:
            integration.get_platform("config_flow")
        except ImportError as err:
            _LOGGER.error(
                "Error occurred loading config flow for integration %s: %s",
                handler_key,
                err,
            )
            raise data_entry_flow.UnknownHandler

        handler = HANDLERS.get(handler_key)

        if handler is None:
            raise data_entry_flow.UnknownHandler

        source = context["source"]

        # Create notification.
        if source in DISCOVERY_SOURCES:
            self.hass.bus.async_fire(EVENT_FLOW_DISCOVERED)
            self.hass.components.persistent_notification.async_create(
                title="New devices discovered",
                message=(
                    "We have discovered new devices on your network. "
                    "[Check it out](/config/integrations)"
                ),
                notification_id=DISCOVERY_NOTIFICATION_ID,
            )

        flow = handler()
        flow.init_step = source
        return flow

    def _async_schedule_save(self) -> None:
        """Save the entity registry to a file."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self):
        """Return data to save."""
        return {"entries": [entry.as_dict() for entry in self._entries]}


async def _old_conf_migrator(old_config):
    """Migrate the pre-0.73 config format to the latest version."""
    return {"entries": old_config}


class ConfigFlow(data_entry_flow.FlowHandler):
    """Base class for config flows with some helpers."""

    CONNECTION_CLASS = CONN_CLASS_UNKNOWN

    @callback
    def _async_current_entries(self):
        """Return current entries."""
        return self.hass.config_entries.async_entries(self.handler)

    @callback
    def _async_in_progress(self):
        """Return other in progress flows for current domain."""
        return [
            flw
            for flw in self.hass.config_entries.flow.async_progress()
            if flw["handler"] == self.handler and flw["flow_id"] != self.flow_id
        ]


class OptionsFlowManager:
    """Flow to set options for a configuration entry."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the options manager."""
        self.hass = hass
        self.flow = data_entry_flow.FlowManager(
            hass, self._async_create_flow, self._async_finish_flow
        )

    async def _async_create_flow(self, entry_id, *, context, data):
        """Create an options flow for a config entry.

        Entry_id and flow.handler is the same thing to map entry with flow.
        """
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return
        flow = HANDLERS[entry.domain].async_get_options_flow(entry.data, entry.options)
        return flow

    async def _async_finish_flow(self, flow, result):
        """Finish an options flow and update options for configuration entry.

        Flow.handler and entry_id is the same thing to map flow with entry.
        """
        entry = self.hass.config_entries.async_get_entry(flow.handler)
        if entry is None:
            return
        self.hass.config_entries.async_update_entry(entry, options=result["data"])

        result["result"] = True
        return result
