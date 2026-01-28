"""The HEMS echonet lite integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timedelta
import logging
import time
from typing import Final

from pyhems.definitions import DefinitionsLoadError, load_definitions_registry
from pyhems.runtime import (
    HemsClient,
    HemsErrorEvent,
    HemsFrameEvent,
    HemsInstanceListEvent,
    RuntimeEvent,
)

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ENABLE_EXPERIMENTAL,
    CONF_INTERFACE,
    CONF_POLL_INTERVAL,
    DEFAULT_INTERFACE,
    DEFAULT_POLL_INTERVAL,
    DISCOVERY_INTERVAL,
    DOMAIN,
    EPC_MANUFACTURER_CODE,
    EPC_PRODUCT_CODE,
    EPC_SERIAL_NUMBER,
    ISSUE_RUNTIME_CLIENT_ERROR,
    ISSUE_RUNTIME_INACTIVE,
    RUNTIME_MONITOR_INTERVAL,
    RUNTIME_MONITOR_MAX_SILENCE,
)
from .coordinator import EchonetLiteCoordinator
from .poller import EchonetLitePropertyPoller
from .types import EchonetLiteConfigEntry, EchonetLiteRuntimeData, RuntimeHealth

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: Final = [
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the HEMS echonet lite integration and ensure a config entry exists."""
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(  # fire-and-forget
                DOMAIN,
                context={"source": SOURCE_IMPORT},
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EchonetLiteConfigEntry) -> bool:
    """Set up HEMS echonet lite from a config entry."""

    # Get options
    interface = entry.options.get(CONF_INTERFACE, DEFAULT_INTERFACE)
    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    enable_experimental = entry.options.get(CONF_ENABLE_EXPERIMENTAL, False)

    _LOGGER.debug("Setting up ECHONET Lite with interface %s", interface)

    # Load device definitions from pyhems
    try:
        definitions = await hass.async_add_executor_job(load_definitions_registry)
    except DefinitionsLoadError as err:
        raise ConfigEntryNotReady(
            "Device definitions file could not be loaded"
        ) from err

    # Build device-specific EPC sets for polling/notification
    monitored_epcs: dict[int, frozenset[int]] = {
        class_code: frozenset(e.epc for e in entities)
        for class_code, entities in definitions.entities.items()
    }

    _LOGGER.debug(
        "Monitored EPCs (polling/notification) per device class: %s",
        {hex(k): " ".join(f"{e:02x}" for e in v) for k, v in monitored_epcs.items()},
    )

    # EPCs to request during node discovery (in addition to identification and instance list)
    discovery_epcs = [EPC_MANUFACTURER_CODE, EPC_PRODUCT_CODE, EPC_SERIAL_NUMBER]

    client = HemsClient(
        interface=interface,
        poll_interval=DISCOVERY_INTERVAL,
        extra_epcs=discovery_epcs,
    )
    coordinator = EchonetLiteCoordinator(
        hass,
        config_entry=entry,
        client=client,
        monitored_epcs=monitored_epcs,
        enable_experimental=enable_experimental,
    )

    runtime_health = RuntimeHealth()
    restart_lock = asyncio.Lock()

    issue_monitor = _RuntimeIssueMonitor(
        hass,
        coordinator,
        threshold=RUNTIME_MONITOR_MAX_SILENCE.total_seconds(),
        interval=RUNTIME_MONITOR_INTERVAL,
    )

    async def _async_restart_runtime() -> None:
        if restart_lock.locked():
            return
        async with restart_lock:
            runtime_health.restart_attempts += 1
            try:
                await client.stop()
            except (
                OSError,
                RuntimeError,
            ) as err:  # pragma: no cover - best effort cleanup
                _LOGGER.debug("Failed to stop ECHONET Lite runtime client: %s", err)
            try:
                await client.start()
            except OSError as err:
                _LOGGER.error("Failed to restart ECHONET Lite runtime client: %s", err)
                runtime_health.last_client_error = str(err)
                runtime_health.last_client_error_at = time.monotonic()
                issue_monitor.record_client_error(str(err))
                return
            runtime_health.last_restart_at = time.monotonic()
            issue_monitor.clear_client_error()
            # Initialize with empty state; nodes are discovered through runtime events
            coordinator.async_set_updated_data({})

    def _handle_runtime_event(event: RuntimeEvent) -> None:
        """Handle runtime events without blocking the receiver loop.

        This is a synchronous callback that schedules all processing as
        background tasks. This ensures pyhems' _dispatch() method doesn't
        await this callback, allowing the receiver loop to continue
        immediately.
        """
        # Previously used to measure event processing duration; removed to
        # reduce log noise and avoid unused variables.

        if isinstance(event, HemsFrameEvent):

            async def _process_frame() -> None:
                await coordinator.async_process_frame_event(event)
                issue_monitor.record_activity(event.received_at)

            # Schedule frame processing as background task to avoid
            # blocking receiver loop
            hass.async_create_task(_process_frame(), name="echonet_lite_process_frame")
            return

        if isinstance(event, HemsInstanceListEvent):
            _LOGGER.debug(
                "Runtime event: HemsInstanceListEvent from %s with %d instances",
                event.node_id,
                len(event.instances),
            )

            async def _process_instance_list() -> None:
                await coordinator.async_process_instance_list_event(event)
                issue_monitor.record_activity(event.received_at)

            # Schedule instance list processing as background task to avoid
            # blocking receiver loop
            hass.async_create_task(
                _process_instance_list(), name="echonet_lite_process_instance_list"
            )
            return

        if isinstance(event, HemsErrorEvent):
            runtime_health.last_client_error = str(event.error)
            runtime_health.last_client_error_at = event.received_at
            _LOGGER.warning(
                "ECHONET Lite runtime client encountered an error: %s", event.error
            )

            async def _handle_error() -> None:
                issue_monitor.record_client_error(str(event.error))
                await _async_restart_runtime()

            # Schedule error handling as background task
            hass.async_create_task(_handle_error(), name="echonet_lite_handle_error")

    unsubscribe_runtime = client.subscribe(_handle_runtime_event)

    try:
        await client.start()
    except OSError as err:
        unsubscribe_runtime()
        raise ConfigEntryNotReady(f"Failed to start runtime client: {err}") from err

    # Initialize with empty state; nodes are discovered through runtime events
    coordinator.async_set_updated_data({})

    issue_monitor.start()

    # Property poller requests EPCs defined in node.poll_epcs (computed at node creation)
    property_poller = EchonetLitePropertyPoller(
        hass, coordinator, client, poll_interval=poll_interval
    )
    discovery_task = hass.async_create_task(client.async_probe_nodes())

    entry.runtime_data = EchonetLiteRuntimeData(
        interface=interface,
        definitions=definitions,
        coordinator=coordinator,
        client=client,
        unsubscribe_runtime=unsubscribe_runtime,
        property_poller=property_poller,
        issue_monitor=issue_monitor,
        health=runtime_health,
        discovery_task=discovery_task,
    )

    # Reload entry when options change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: EchonetLiteConfigEntry
) -> None:
    """Handle options update by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: EchonetLiteConfigEntry
) -> bool:
    """Unload a config entry."""
    runtime = entry.runtime_data
    if runtime:
        runtime.unsubscribe_runtime()
        runtime.issue_monitor.stop()
        runtime.property_poller.stop()
        runtime.discovery_task.cancel()
        with suppress(asyncio.CancelledError):
            await runtime.discovery_task

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if runtime:
        await runtime.client.stop()

    return unload_ok


class _RuntimeIssueMonitor:
    """Monitor runtime activity and surface repair issues."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: EchonetLiteCoordinator,
        *,
        threshold: float,
        interval: timedelta,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._hass = hass
        self._coordinator = coordinator
        self._threshold = threshold
        self._interval = interval
        self._monotonic = monotonic
        self._cancel_interval: Callable[[], None] | None = None
        self._inactivity_issue_active = False
        self._client_issue_active = False

    def start(self) -> None:
        """Begin checking for runtime inactivity."""
        if self._cancel_interval is None:
            self._cancel_interval = async_track_time_interval(
                self._hass, self._async_check_runtime, self._interval
            )

    def stop(self) -> None:
        """Stop monitoring and clear any active issue."""
        if self._cancel_interval:
            self._cancel_interval()
            self._cancel_interval = None
        self._clear_inactivity_issue_if_needed()
        self.clear_client_error()

    @callback
    def record_activity(self, timestamp: float) -> None:
        """Note that activity was observed and clear issues if present."""
        self._coordinator.last_frame_received_at = timestamp
        self._clear_inactivity_issue_if_needed()

    @callback
    def _async_check_runtime(self, _now: datetime) -> None:
        last = self._coordinator.last_frame_received_at
        if last is None:
            return
        if self._monotonic() - last < self._threshold:
            self._clear_inactivity_issue_if_needed()
            return
        if self._inactivity_issue_active:
            return
        minutes = max(int(self._threshold // 60), 1)
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            ISSUE_RUNTIME_INACTIVE,
            issue_domain=DOMAIN,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="runtime_inactive",
            translation_placeholders={"minutes": str(minutes)},
        )
        self._inactivity_issue_active = True

    @callback
    def _clear_inactivity_issue_if_needed(self) -> None:
        if self._inactivity_issue_active:
            ir.async_delete_issue(self._hass, DOMAIN, ISSUE_RUNTIME_INACTIVE)
            self._inactivity_issue_active = False

    @callback
    def record_client_error(self, message: str) -> None:
        """Create a repair issue describing the runtime client failure."""
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            ISSUE_RUNTIME_CLIENT_ERROR,
            issue_domain=DOMAIN,
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="runtime_client_error",
            translation_placeholders={"error": message},
        )
        self._client_issue_active = True

    @callback
    def clear_client_error(self) -> None:
        """Clear any existing runtime client error issue."""
        if self._client_issue_active:
            ir.async_delete_issue(self._hass, DOMAIN, ISSUE_RUNTIME_CLIENT_ERROR)
            self._client_issue_active = False
