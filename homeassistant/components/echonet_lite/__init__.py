"""The HEMS Echonet Lite integration.

``iot_class`` is ``local_polling`` because ECHONET Lite is fundamentally a
request/response protocol over local UDP multicast. Status acquisition is
done with GET (ESV 0x62) and the response GET_RES (0x72).

The specification also defines unsolicited notifications INF (ESV 0x73) and
INFC (0x74), but their use is constrained: APPENDIX "Detailed Requirements
for ECHONET Device Objects" marks each property with an "Announcement at
Status Change" flag, and only properties bearing that flag may be pushed.
The flag is set on a minority of properties -- typically operating status
and a handful of mode/state EPCs -- while measured values (temperatures,
instantaneous power, cumulative energy meters, consumables, ...), numeric
setpoints and most configuration items are *not* announceable and can only
be obtained via GET. Whether a vendor implementation actually emits INF for
its announceable properties is additionally left to the implementation.

As a consequence this integration is polling-first: ``PropertyPoller`` runs
a per-device GET loop at ``DEFAULT_POLL_INTERVAL`` (60 s), and INF frames --
when they arrive -- are treated as a free push-based optimization on top.
The poll set is automatically reduced to ``get_epcs - inf_epcs`` per device
so properties the device does actively push are not re-polled.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timedelta
import logging
import time
from typing import Any, Final

from pyhems import (
    DefinitionsLoadError,
    DeviceManager,
    HemsClient,
    HemsErrorEvent,
    HemsFrameEvent,
    HemsInstanceListEvent,
    PropertyPoller,
    RuntimeEvent,
    load_definitions_registry,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ENABLE_EXPERIMENTAL,
    CONF_INTERFACE,
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
    STABLE_CLASS_CODES,
)
from .coordinator import EchonetLiteCoordinator
from .types import EchonetLiteConfigEntry, EchonetLiteRuntimeData, RuntimeHealth

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: Final = [
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HEMS Echonet Lite integration."""
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: EchonetLiteConfigEntry
) -> bool:
    """Migrate old config entry to new format."""
    if entry.version == 1 and entry.minor_version < 1:
        # Version 1.0 → 1.1: Move CONF_INTERFACE from options to data
        new_data = dict(entry.data)
        new_options = dict(entry.options)
        if CONF_INTERFACE in new_options:
            new_data[CONF_INTERFACE] = new_options.pop(CONF_INTERFACE)
        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options, minor_version=1
        )
        _LOGGER.debug("Migrated config entry to version 1.1")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EchonetLiteConfigEntry) -> bool:
    """Set up HEMS Echonet Lite from a config entry."""

    interface = entry.data.get(CONF_INTERFACE, DEFAULT_INTERFACE)
    enable_experimental = entry.options.get(CONF_ENABLE_EXPERIMENTAL, False)

    _LOGGER.debug("Setting up ECHONET Lite with interface %s", interface)

    # Load device definitions from pyhems
    try:
        definitions = await hass.async_add_executor_job(load_definitions_registry)
    except DefinitionsLoadError as err:
        raise ConfigEntryError("Device definitions file could not be loaded") from err

    # Build device-specific EPC sets for polling/notification
    # Start with definitions-based EPCs (MRA + vendor)
    monitored_epcs: dict[int, frozenset[int]] = {
        class_code: frozenset(entity_def.epc for entity_def in entity_defs)
        for class_code, entity_defs in definitions.entities.items()
    }

    _LOGGER.debug(
        "Monitored EPCs (polling/notification) per device class: %s",
        {
            hex(class_code): " ".join(f"{epc:02x}" for epc in epcs)
            for class_code, epcs in monitored_epcs.items()
        },
    )

    # EPCs to request during node discovery (in addition to identification and instance list)
    discovery_epcs = [EPC_MANUFACTURER_CODE, EPC_PRODUCT_CODE, EPC_SERIAL_NUMBER]

    client = HemsClient(
        interface=interface,
        poll_interval=DISCOVERY_INTERVAL,
        extra_epcs=discovery_epcs,
    )

    # Determine which device class codes to accept
    class_code_filter: frozenset[int] | None = None
    if not enable_experimental:
        class_code_filter = STABLE_CLASS_CODES

    device_manager = DeviceManager(
        client=client,
        monitored_epcs=monitored_epcs,
        definitions=definitions,
        class_code_filter=class_code_filter,
    )
    coordinator = EchonetLiteCoordinator(
        hass,
        config_entry=entry,
        device_manager=device_manager,
    )

    # Wire DeviceManager callbacks to coordinator
    @callback
    def _on_device_added(device_key: str) -> None:
        """Handle new device from DeviceManager."""
        # ``async_set_updated_data`` is the documented contract for publishing
        # new data on ``DataUpdateCoordinator``; it also notifies listeners so
        # existing entities re-render. Notify the device-added listeners
        # afterwards so platforms can create entities for the new device.
        coordinator.async_set_updated_data(dict(device_manager.data))
        coordinator.async_notify_device_added(device_key)

    @callback
    def _on_device_updated(device_key: str) -> None:
        """Handle property update from DeviceManager."""
        coordinator.async_update_listeners()

    device_manager.on_device_added(_on_device_added)
    device_manager.on_device_updated(_on_device_updated)

    runtime_health = RuntimeHealth()

    issue_monitor = _RuntimeIssueMonitor(
        hass,
        coordinator,
        threshold=RUNTIME_MONITOR_MAX_SILENCE.total_seconds(),
        interval=RUNTIME_MONITOR_INTERVAL,
    )

    controller = _RuntimeController(
        hass,
        entry,
        client=client,
        device_manager=device_manager,
        coordinator=coordinator,
        issue_monitor=issue_monitor,
        health=runtime_health,
    )

    await controller.async_start()

    property_poller = PropertyPoller(
        device_manager, poll_interval=DEFAULT_POLL_INTERVAL
    )
    property_poller.start()

    entry.runtime_data = EchonetLiteRuntimeData(
        definitions=definitions,
        coordinator=coordinator,
        client=client,
        unsubscribe_runtime=controller.unsubscribe_runtime,
        property_poller=property_poller,
        issue_monitor=issue_monitor,
        health=runtime_health,
        discovery_task=controller.discovery_task,
        event_consumer_task=controller.event_consumer_task,
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
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    runtime = entry.runtime_data
    if runtime:
        runtime.unsubscribe_runtime()
        runtime.issue_monitor.stop()
        runtime.property_poller.stop()
        runtime.discovery_task.cancel()
        with suppress(asyncio.CancelledError):
            await runtime.discovery_task
        runtime.event_consumer_task.cancel()
        with suppress(asyncio.CancelledError):
            await runtime.event_consumer_task
        await runtime.client.stop()

    return True


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
        """Begin checking for runtime inactivity.

        Seeds ``last_runtime_activity_at`` with the current monotonic time so
        that a total absence of incoming frames (never a single activity
        observed) still trips the threshold. Without this baseline the
        inactivity check silently skips every tick while
        ``last_runtime_activity_at is None``.
        """
        if self._cancel_interval is not None:
            return
        self.record_activity(self._monotonic())
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
        self._coordinator.record_runtime_activity(timestamp)
        self._clear_inactivity_issue_if_needed()

    @callback
    def _async_check_runtime(self, _now: datetime) -> None:
        last_activity_at = self._coordinator.last_runtime_activity_at
        if last_activity_at is None:
            return
        if self._monotonic() - last_activity_at < self._threshold:
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
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="runtime_inactive",
            translation_placeholders={"minutes": str(minutes)},
        )
        _LOGGER.warning(
            "No ECHONET Lite frames received for %d minutes; devices may be offline",
            minutes,
        )
        self._inactivity_issue_active = True
        # Entity ``available`` depends on the same silence threshold. Push a
        # listener update so entities re-evaluate availability right away
        # instead of waiting for the next frame (which, by definition, is
        # not arriving).
        self._coordinator.async_update_listeners()

    @callback
    def _clear_inactivity_issue_if_needed(self) -> None:
        if self._inactivity_issue_active:
            ir.async_delete_issue(self._hass, DOMAIN, ISSUE_RUNTIME_INACTIVE)
            self._inactivity_issue_active = False
            _LOGGER.info("ECHONET Lite communication restored")

    @callback
    def record_client_error(self, message: str) -> None:
        """Create a repair issue describing the runtime client failure."""
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            ISSUE_RUNTIME_CLIENT_ERROR,
            issue_domain=DOMAIN,
            is_fixable=False,
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


class _RuntimeController:
    """Own the pyhems runtime lifecycle for a config entry.

    Encapsulates the restart lock, event queue, event consumer task and
    discovery task so that ``async_setup_entry`` can stay focused on
    dependency wiring.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EchonetLiteConfigEntry,
        *,
        client: HemsClient,
        device_manager: DeviceManager,
        coordinator: EchonetLiteCoordinator,
        issue_monitor: _RuntimeIssueMonitor,
        health: RuntimeHealth,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._client = client
        self._device_manager = device_manager
        self._coordinator = coordinator
        self._issue_monitor = issue_monitor
        self._health = health
        self._restart_lock = asyncio.Lock()
        self._event_queue: asyncio.Queue[RuntimeEvent] = asyncio.Queue()
        self._unsubscribe_runtime: Callable[[], None] | None = None
        self._discovery_task: asyncio.Task[Any] | None = None
        self._event_consumer_task: asyncio.Task[None] | None = None

    @property
    def unsubscribe_runtime(self) -> Callable[[], None]:
        """Return the runtime-event unsubscribe callback."""
        assert self._unsubscribe_runtime is not None
        return self._unsubscribe_runtime

    @property
    def discovery_task(self) -> asyncio.Task[Any]:
        """Return the node discovery background task."""
        assert self._discovery_task is not None
        return self._discovery_task

    @property
    def event_consumer_task(self) -> asyncio.Task[None]:
        """Return the runtime event consumer background task."""
        assert self._event_consumer_task is not None
        return self._event_consumer_task

    async def async_start(self) -> None:
        """Subscribe, start the client and spawn background tasks."""
        self._unsubscribe_runtime = self._client.subscribe(self._handle_runtime_event)
        try:
            await self._client.start()
        except OSError as err:
            self._unsubscribe_runtime()
            self._unsubscribe_runtime = None
            raise ConfigEntryNotReady(f"Failed to start runtime client: {err}") from err

        # Initialize with empty state; nodes are discovered through runtime events
        self._coordinator.async_set_updated_data({})

        # ``_RuntimeIssueMonitor.start`` seeds the inactivity baseline with
        # the current monotonic time so that a cold start with zero frames
        # still trips the threshold.
        self._issue_monitor.start()

        self._discovery_task = self._entry.async_create_background_task(
            self._hass,
            self._client.probe_nodes(),
            name="echonet_lite_discovery",
        )
        self._event_consumer_task = self._entry.async_create_background_task(
            self._hass,
            self._consume_runtime_events(),
            name="echonet_lite_event_consumer",
        )

    @callback
    def _handle_runtime_event(self, event: RuntimeEvent) -> None:
        """Enqueue runtime events for the single consumer task.

        Kept synchronous and non-blocking so that pyhems' receiver loop
        continues immediately.
        """
        self._event_queue.put_nowait(event)

    async def _consume_runtime_events(self) -> None:
        """Serialize runtime event processing.

        Using a single consumer preserves the arrival order of
        ``HemsInstanceListEvent`` (device registration) and
        ``HemsFrameEvent`` (property updates) so that frames for a newly
        announced device are never applied before the device itself is
        registered in ``DeviceManager``.
        """
        while True:
            event = await self._event_queue.get()
            try:
                if isinstance(event, HemsFrameEvent):
                    await self._coordinator.async_process_frame_event(event)
                    self._issue_monitor.record_activity(event.received_at)
                elif isinstance(event, HemsInstanceListEvent):
                    _LOGGER.debug(
                        "Runtime event: HemsInstanceListEvent from %s with %d instances",
                        event.node_id,
                        len(event.instances),
                    )
                    await self._coordinator.async_process_instance_list_event(event)
                    self._issue_monitor.record_activity(event.received_at)
                elif isinstance(event, HemsErrorEvent):
                    self._health.last_client_error = str(event.error)
                    self._health.last_client_error_at = event.received_at
                    _LOGGER.warning(
                        "ECHONET Lite runtime client encountered an error: %s",
                        event.error,
                    )
                    self._issue_monitor.record_client_error(str(event.error))
                    await self._async_restart_runtime()
            except OSError, LookupError, TypeError, ValueError:
                # Narrow to the fault classes realistic for frame parsing
                # and dispatch (I/O, missing keys, malformed payloads).
                # Programmer errors (RuntimeError, AssertionError, ...) are
                # intentionally allowed to propagate so the task fails
                # loudly instead of silently swallowing bugs.
                _LOGGER.exception(
                    "Failed to process ECHONET Lite runtime event: %r", event
                )
            finally:
                self._event_queue.task_done()

    async def _async_restart_runtime(self) -> None:
        """Restart the pyhems runtime client, debouncing concurrent callers."""
        if self._restart_lock.locked():
            return
        async with self._restart_lock:
            self._health.restart_attempts += 1
            try:
                await self._client.stop()
            except (
                OSError,
                RuntimeError,
            ) as err:  # pragma: no cover - best effort cleanup
                _LOGGER.debug("Failed to stop ECHONET Lite runtime client: %s", err)
            try:
                await self._client.start()
            except OSError as err:
                _LOGGER.error("Failed to restart ECHONET Lite runtime client: %s", err)
                self._health.last_client_error = str(err)
                self._health.last_client_error_at = time.monotonic()
                self._issue_monitor.record_client_error(str(err))
                return
            self._health.last_restart_at = time.monotonic()
            self._issue_monitor.clear_client_error()
            # Treat a successful restart as activity so the inactivity issue
            # (if any) is cleared immediately instead of waiting for the
            # next incoming frame.
            self._issue_monitor.record_activity(time.monotonic())
            # Re-publish the current DeviceManager state so entities for
            # already-known devices stay available after the restart.
            # DeviceManager retains its ``data`` across client stop/start,
            # so clearing the coordinator here would make those entities
            # disappear silently until each device is re-announced.
            self._coordinator.async_set_updated_data(dict(self._device_manager.data))
