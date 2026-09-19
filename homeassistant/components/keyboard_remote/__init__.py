"""Receive signals from a keyboard and use it as a remote control."""

import asyncio
from collections.abc import Callable, Coroutine
from contextlib import suppress
import logging
import os
from typing import TYPE_CHECKING, Any

from asyncinotify import Inotify, Mask
import probatio

if TYPE_CHECKING:
    from evdev import InputDevice

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Event,
    HomeAssistant,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_DEVICE_DESCRIPTOR,
    CONF_DEVICE_NAME,
    CONF_DEVICE_PATH,
    CONF_EMULATE_KEY_HOLD,
    CONF_EMULATE_KEY_HOLD_DELAY,
    CONF_EMULATE_KEY_HOLD_REPEAT,
    CONF_KEY_TYPES,
    DEFAULT_EMULATE_KEY_HOLD,
    DEFAULT_EMULATE_KEY_HOLD_DELAY,
    DEFAULT_EMULATE_KEY_HOLD_REPEAT,
    DEFAULT_KEY_TYPES,
    DEVINPUT,
    DOMAIN,
    EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED,
    EVENT_KEYBOARD_REMOTE_CONNECTED,
    EVENT_KEYBOARD_REMOTE_DISCONNECTED,
    KEY_CODE,
    KEY_VALUE,
    KEY_VALUE_NAME,
    MATCH_DEVICE_NAME,
    MATCH_DEVICE_PATH,
    MATCH_YAML_DESCRIPTOR,
)

_LOGGER = logging.getLogger(__name__)

DATA_MANAGER: HassKey[KeyboardRemoteManager] = HassKey(DOMAIN)

# Legacy YAML constants (used only for CONFIG_SCHEMA parsing)
_DEVICE_DESCRIPTOR = "device_descriptor"
_DEVICE_ID_GROUP = "Device description"
_DEVICE_NAME = "device_name"
_TYPE = "type"
_EMULATE_KEY_HOLD = "emulate_key_hold"
_EMULATE_KEY_HOLD_DELAY = "emulate_key_hold_delay"
_EMULATE_KEY_HOLD_REPEAT = "emulate_key_hold_repeat"

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.All(
            cv.ensure_list,
            [
                probatio.Schema(
                    {
                        probatio.Exclusive(
                            _DEVICE_DESCRIPTOR, _DEVICE_ID_GROUP
                        ): cv.string,
                        probatio.Exclusive(_DEVICE_NAME, _DEVICE_ID_GROUP): cv.string,
                        probatio.Optional(_TYPE, default=["key_up"]): probatio.All(
                            cv.ensure_list, [probatio.In(KEY_VALUE)]
                        ),
                        probatio.Optional(_EMULATE_KEY_HOLD, default=False): cv.boolean,
                        probatio.Optional(
                            _EMULATE_KEY_HOLD_DELAY, default=0.250
                        ): float,
                        probatio.Optional(
                            _EMULATE_KEY_HOLD_REPEAT, default=0.033
                        ): float,
                    }
                ),
                cv.has_at_least_one_key(_DEVICE_DESCRIPTOR, _DEVICE_NAME),
            ],
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Keyboard Remote from YAML (triggers import only)."""
    if DOMAIN not in config:
        return True

    for dev_block in config[DOMAIN]:
        hass.async_create_task(_async_import_yaml_device(hass, dev_block))

    return True


async def _async_import_yaml_device(
    hass: HomeAssistant, dev_block: dict[str, Any]
) -> None:
    """Import a single YAML device block and create deprecation issues."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=dev_block,
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and (reason := result.get("reason", "unknown")) != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{reason}",
            breaks_in_ha_version="2027.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{reason}",
            translation_placeholders={
                "url": f"/config/integrations/dashboard/add?domain={DOMAIN}"
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.4.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Keyboard Remote",
        },
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a single keyboard remote device from a config entry."""
    # Get or create the shared manager
    if (manager := hass.data.get(DATA_MANAGER)) is None:
        manager = KeyboardRemoteManager(hass)
        hass.data[DATA_MANAGER] = manager

    # Create the device handler for this entry and register it
    handler = DeviceHandler(hass, entry)
    manager.register_handler(entry.entry_id, handler)

    # Start the manager when HA is running (idempotent — first call starts,
    # subsequent calls are no-ops). async_at_start fires immediately if HA
    # is already running, or waits for EVENT_HOMEASSISTANT_START.
    async def _start_manager(hass: HomeAssistant) -> None:
        await manager.async_start()

    entry.async_on_unload(async_at_start(hass, _start_manager))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a keyboard remote config entry."""
    manager = hass.data[DATA_MANAGER]
    await manager.unregister_handler(entry.entry_id)

    # If this was the last loaded entry, tear down the shared manager
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        await manager.async_stop()
        hass.data.pop(DATA_MANAGER, None)

    return True


class KeyboardRemoteManager:
    """Shared inotify manager for all keyboard_remote config entries.

    Created by the first config entry to load. Destroyed when the last
    config entry unloads.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the shared manager."""
        self.hass = hass
        self._lock = asyncio.Lock()
        self._handlers: dict[str, DeviceHandler] = {}  # entry_id -> handler
        self._active_handlers_by_descriptor: dict[str, DeviceHandler] = {}
        self._inotify: Inotify | None = None
        self._watcher: Any = None
        self._monitor_task: asyncio.Task | None = None
        self._stop_listener: CALLBACK_TYPE | None = None
        self._started = False

    async def async_start(self) -> None:
        """Start the inotify watcher (idempotent, lock-protected)."""
        async with self._lock:
            if self._started:
                return

            _LOGGER.debug("Start monitoring")

            # Config entries are not unloaded when Home Assistant stops, so
            # without this the devices are never ungrabbed on shutdown.
            self._stop_listener = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._async_handle_hass_stop
            )

            self._inotify = Inotify()
            self._watcher = self._inotify.add_watch(
                DEVINPUT, Mask.CREATE | Mask.ATTRIB | Mask.DELETE
            )

            # Scan initial devices AFTER starting watcher to avoid race
            # conditions leading to missing device connections
            await self._async_scan_initial_devices()

            self._monitor_task = self.hass.async_create_task(
                self._async_monitor_devices()
            )
            self._started = True

    async def _async_handle_hass_stop(self, event: Event) -> None:
        """Tear down when Home Assistant stops."""
        self._stop_listener = None
        await self.async_stop()

    async def async_stop(self) -> None:
        """Stop the inotify watcher and all device handlers."""
        async with self._lock:
            if not self._started:
                return

            _LOGGER.debug("Cleanup on shutdown")

            if self._stop_listener is not None:
                self._stop_listener()
                self._stop_listener = None

            if self._inotify and self._watcher:
                self._inotify.rm_watch(self._watcher)
                self._watcher = None

            if self._monitor_task is not None:
                if not self._monitor_task.done():
                    self._monitor_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._monitor_task
                self._monitor_task = None

            # Stop all active device handlers
            stop_tasks = {
                self.hass.async_create_task(handler.async_device_stop_monitoring())
                for handler in self._active_handlers_by_descriptor.values()
            }
            if stop_tasks:
                await asyncio.wait(stop_tasks)
            self._active_handlers_by_descriptor.clear()

            if self._inotify:
                self._inotify.close()
                self._inotify = None

            self._started = False

    async def _async_release_failed_handler(self, handler: DeviceHandler) -> None:
        """Free a handler whose device stopped being readable.

        The handler stays registered so a later device event can rebind it.
        """
        for descriptor in [
            desc
            for desc, active in self._active_handlers_by_descriptor.items()
            if active is handler
        ]:
            del self._active_handlers_by_descriptor[descriptor]
        await handler.async_device_stop_monitoring(from_monitor_task=True)

    def register_handler(self, entry_id: str, handler: DeviceHandler) -> None:
        """Register a DeviceHandler for a config entry."""
        self._handlers[entry_id] = handler
        handler.set_monitor_failure_callback(self._async_release_failed_handler)
        # If already started, check if this handler's device is connected
        if self._started:
            self.hass.async_create_task(self._async_check_handler(handler))

    async def unregister_handler(self, entry_id: str) -> None:
        """Unregister a DeviceHandler and stop its monitoring."""
        handler = self._handlers.pop(entry_id, None)
        if handler is None:
            return
        # Remove from active handlers
        descriptors_to_remove = [
            desc
            for desc, h in self._active_handlers_by_descriptor.items()
            if h is handler
        ]
        for desc in descriptors_to_remove:
            del self._active_handlers_by_descriptor[desc]
        await handler.async_device_stop_monitoring()

    def _get_handler_for_device(
        self, descriptor: str, handlers: list[DeviceHandler]
    ) -> tuple[InputDevice | None, DeviceHandler | None]:
        """Find the best matching handler for a device descriptor (path).

        The handlers list must be a snapshot taken on the event loop thread
        to avoid race conditions with register/unregister.
        """
        from evdev import InputDevice  # noqa: PLC0415

        # Devices are often added and then correct permissions set after
        try:
            dev = InputDevice(descriptor)
        except OSError:
            return (None, None)

        best_handler: DeviceHandler | None = None
        best_rank: int | None = None
        for handler in handlers:
            rank = handler.match_rank(descriptor, dev)
            if rank is None:
                continue
            if best_rank is None or rank < best_rank:
                best_handler, best_rank = handler, rank

        if best_handler is None:
            dev.close()
            return (None, None)

        return (dev, best_handler)

    def _scan_and_match_devices(
        self, handlers: list[DeviceHandler]
    ) -> list[tuple[str, InputDevice, DeviceHandler]]:
        """List all devices and give each handler its strongest match.

        Every candidate is ranked before anything is assigned. Matching device
        by device instead would let a name match on one node of a composite
        keyboard claim the handler before its exact device_path match is
        reached, and list_devices() returns nodes in arbitrary order.
        """
        from evdev import InputDevice, list_devices  # noqa: PLC0415

        opened: dict[str, InputDevice] = {}
        candidates: list[tuple[int, str, DeviceHandler]] = []
        for descriptor in list_devices(DEVINPUT):
            try:
                dev = InputDevice(descriptor)
            except OSError:
                continue
            opened[descriptor] = dev
            candidates.extend(
                (rank, descriptor, handler)
                for handler in handlers
                if (rank := handler.match_rank(descriptor, dev)) is not None
            )

        matches: list[tuple[str, InputDevice, DeviceHandler]] = []
        claimed_handlers: set[DeviceHandler] = set()
        claimed_descriptors: set[str] = set()
        # Sort on descriptor as well so equally ranked candidates resolve the
        # same way on every scan.
        for _rank, descriptor, handler in sorted(candidates, key=lambda c: c[:2]):
            if handler in claimed_handlers or descriptor in claimed_descriptors:
                continue
            claimed_handlers.add(handler)
            claimed_descriptors.add(descriptor)
            matches.append((descriptor, opened[descriptor], handler))

        for descriptor, dev in opened.items():
            if descriptor not in claimed_descriptors:
                dev.close()

        return matches

    async def _async_scan_initial_devices(self) -> None:
        """Scan all current /dev/input/ devices and start matching handlers."""
        handlers = list(self._handlers.values())
        matches = await self.hass.async_add_executor_job(
            self._scan_and_match_devices, handlers
        )

        start_tasks: set[asyncio.Task] = set()
        for descriptor, dev, handler in matches:
            if not self._claim_descriptor(descriptor, dev, handler):
                continue
            start_tasks.add(
                self.hass.async_create_task(handler.async_device_start_monitoring(dev))
            )

        if start_tasks:
            await asyncio.wait(start_tasks)

    def _find_device_for_handler(
        self,
        handler: DeviceHandler,
        handlers: list[DeviceHandler],
        skip_descriptors: set[str],
    ) -> tuple[str, InputDevice] | None:
        """Find the best connected device matching a handler (runs in executor)."""
        from evdev import list_devices  # noqa: PLC0415

        best: tuple[int, str, InputDevice] | None = None
        for descriptor in sorted(list_devices(DEVINPUT)):
            if descriptor in skip_descriptors:
                continue
            dev, matched = self._get_handler_for_device(descriptor, handlers)
            if dev is None:
                continue
            rank = handler.match_rank(descriptor, dev) if matched is handler else None
            if rank is None or (best is not None and rank >= best[0]):
                dev.close()
                continue
            if best is not None:
                best[2].close()
            best = (rank, descriptor, dev)

        if best is None:
            return None
        return (best[1], best[2])

    def _claim_descriptor(
        self, descriptor: str, dev: InputDevice, handler: DeviceHandler
    ) -> bool:
        """Assign a descriptor to a handler, or close the device and refuse.

        Callers reach here after an executor job that yielded to the event
        loop, so the entry may have unloaded, another task may have taken the
        descriptor, and the handler may already have a device. Starting a
        second descriptor on a monitoring handler is the damaging case: the
        extra mapping makes a later DELETE of that node stop the device the
        handler is really reading from.
        """
        if (
            self._handlers.get(handler.entry.entry_id) is not handler
            or descriptor in self._active_handlers_by_descriptor
            or handler.is_monitoring
        ):
            dev.close()
            return False

        self._active_handlers_by_descriptor[descriptor] = handler
        return True

    async def _async_check_handler(self, handler: DeviceHandler) -> None:
        """Check if a newly registered handler's device is currently connected."""
        handlers = list(self._handlers.values())
        skip = set(self._active_handlers_by_descriptor)
        result = await self.hass.async_add_executor_job(
            self._find_device_for_handler, handler, handlers, skip
        )
        if result is not None:
            descriptor, dev = result
            if self._claim_descriptor(descriptor, dev, handler):
                await handler.async_device_start_monitoring(dev)

    async def _async_monitor_devices(self) -> None:
        """Monitor /dev/input/ for device add/remove events via inotify."""
        _LOGGER.debug("Start monitoring loop")

        assert self._inotify is not None
        try:
            async for event in self._inotify:
                descriptor = f"{DEVINPUT}/{event.name}"
                _LOGGER.debug(
                    "got event for %s: %s",
                    descriptor,
                    event.mask,
                )

                descriptor_active = descriptor in self._active_handlers_by_descriptor

                if (event.mask & Mask.DELETE) and descriptor_active:
                    _LOGGER.debug("removing: %s", descriptor)
                    handler = self._active_handlers_by_descriptor[descriptor]
                    del self._active_handlers_by_descriptor[descriptor]
                    await handler.async_device_stop_monitoring()
                elif (
                    (event.mask & Mask.CREATE) or (event.mask & Mask.ATTRIB)
                ) and not descriptor_active:
                    _LOGGER.debug("checking new: %s", descriptor)
                    handlers = list(self._handlers.values())
                    result = await self.hass.async_add_executor_job(
                        self._get_handler_for_device, descriptor, handlers
                    )
                    if result[0] is None or result[1] is None:
                        continue
                    dev, handler = result[0], result[1]
                    if not self._claim_descriptor(descriptor, dev, handler):
                        continue
                    _LOGGER.debug("adding: %s", descriptor)
                    await handler.async_device_start_monitoring(dev)
        except asyncio.CancelledError:
            _LOGGER.debug("Monitoring canceled")
            return


class DeviceHandler:
    """Manage input events for a single keyboard device (one config entry)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize from config entry data and options."""
        self.hass = hass
        self.entry = entry
        self._monitor_task: asyncio.Task | None = None
        self.dev: InputDevice | None = None
        self._descriptor: str | None = None
        self._on_monitor_failure: (
            Callable[[DeviceHandler], Coroutine[Any, Any, None]] | None
        ) = None

    def set_monitor_failure_callback(
        self, callback: Callable[[DeviceHandler], Coroutine[Any, Any, None]]
    ) -> None:
        """Set what the manager should run if this device stops being readable."""
        self._on_monitor_failure = callback

    @property
    def is_monitoring(self) -> bool:
        """Whether this handler already has a device to read from."""
        return self._monitor_task is not None

    @property
    def _device_path(self) -> str | None:
        """The configured device path (by-id or raw), if the entry has one.

        Name-only YAML imports store no path, because the only path available
        at import time is a transient /dev/input/eventN.
        """
        return self.entry.data.get(CONF_DEVICE_PATH)

    @property
    def _device_name_config(self) -> str | None:
        """The configured device name."""
        return self.entry.data.get(CONF_DEVICE_NAME)

    @property
    def _device_descriptor(self) -> str | None:
        """The original YAML device_descriptor, if any."""
        return self.entry.data.get(CONF_DEVICE_DESCRIPTOR)

    @property
    def _key_values(self) -> set[int]:
        """Key event values to monitor."""
        key_types = self.entry.options.get(CONF_KEY_TYPES, DEFAULT_KEY_TYPES)
        return {KEY_VALUE[kt] for kt in key_types}

    @property
    def _emulate_key_hold(self) -> bool:
        """Whether key hold emulation is enabled."""
        return self.entry.options.get(CONF_EMULATE_KEY_HOLD, DEFAULT_EMULATE_KEY_HOLD)

    @property
    def _emulate_key_hold_delay(self) -> float:
        """Delay before key hold emulation starts."""
        return self.entry.options.get(
            CONF_EMULATE_KEY_HOLD_DELAY, DEFAULT_EMULATE_KEY_HOLD_DELAY
        )

    @property
    def _emulate_key_hold_repeat(self) -> float:
        """Repeat interval for key hold emulation."""
        return self.entry.options.get(
            CONF_EMULATE_KEY_HOLD_REPEAT, DEFAULT_EMULATE_KEY_HOLD_REPEAT
        )

    def match_rank(self, descriptor: str, dev: InputDevice) -> int | None:
        """Return how strongly this handler matches a device, or None.

        Lower ranks are stronger, and callers must prefer the strongest match
        rather than the first one they find. A composite keyboard reports the
        same name on every node it exposes, so a name match alone cannot tell
        the node the user selected from its siblings.
        """
        real_path = os.path.realpath(descriptor)

        # Check by-id or configured path
        device_path = self._device_path
        if (
            device_path
            and os.path.exists(device_path)
            and os.path.realpath(device_path) == real_path
        ):
            return MATCH_DEVICE_PATH

        # Check original YAML descriptor
        yaml_descriptor = self._device_descriptor
        if yaml_descriptor and os.path.realpath(yaml_descriptor) == real_path:
            return MATCH_YAML_DESCRIPTOR

        # Check by device name, but only for entries that have nothing better.
        # An entry configured with a path keeps that identity even while the
        # node is missing, because a composite keyboard reports the same name
        # on every node it exposes and a sibling would be the wrong device.
        if (
            not device_path
            and not yaml_descriptor
            and self._device_name_config
            and dev.name == self._device_name_config
        ):
            return MATCH_DEVICE_NAME

        return None

    def matches_device(self, descriptor: str, dev: InputDevice) -> bool:
        """Check if this handler matches the given device."""
        return self.match_rank(descriptor, dev) is not None

    async def async_device_start_monitoring(self, dev: InputDevice) -> None:
        """Start event monitoring task and fire connected event."""
        _LOGGER.debug("Keyboard async_device_start_monitoring, %s", dev.name)
        if self._monitor_task is not None:
            return

        self.dev = dev
        # Report the path the user configured. An imported YAML descriptor comes
        # first so that automations matching the path from before the migration
        # keep firing, even though the entry now resolves a by-id path too.
        self._descriptor = self._device_descriptor or self._device_path or self.dev.path

        # Not eager: a device that fails immediately would otherwise run the
        # whole monitor body, including the teardown that clears this
        # attribute, before the assignment below overwrites it again.
        self._monitor_task = self.hass.async_create_task(
            self._async_monitor_input(), eager_start=False
        )
        self.hass.bus.async_fire(
            EVENT_KEYBOARD_REMOTE_CONNECTED,
            {
                CONF_DEVICE_DESCRIPTOR: self._descriptor,
                CONF_DEVICE_NAME: dev.name,
            },
        )
        _LOGGER.debug("Keyboard (re-)connected, %s", dev.name)

    async def async_device_stop_monitoring(
        self, *, from_monitor_task: bool = False
    ) -> None:
        """Stop event monitoring task and fire disconnected event.

        Pass from_monitor_task=True when the monitor task itself is tearing
        down after a read failure. It cannot wait for its own completion, and
        ungrabbing a device that just errored would only raise again.
        """
        if self._monitor_task is None:
            return

        dev = self.dev
        assert dev is not None

        if not from_monitor_task:
            with suppress(OSError):
                await self.hass.async_add_executor_job(dev.ungrab)
        # Remove reader and close device before cancelling the task to avoid
        # triggering unhandled exceptions inside evdev coroutines
        self.hass.loop.remove_reader(dev.fileno())
        dev.close()
        task = self._monitor_task
        self._monitor_task = None
        if not from_monitor_task:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self.hass.bus.async_fire(
            EVENT_KEYBOARD_REMOTE_DISCONNECTED,
            {
                CONF_DEVICE_DESCRIPTOR: self._descriptor,
                CONF_DEVICE_NAME: dev.name,
            },
        )
        _LOGGER.debug("Keyboard disconnected, %s", dev.name)
        self.dev = None

    async def _async_keyrepeat(
        self, dev: InputDevice, code: int, delay: float, repeat: float
    ) -> None:
        """Emulate keyboard delay/repeat by firing key hold events on a timer."""
        await asyncio.sleep(delay)
        while True:
            self.hass.bus.async_fire(
                EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED,
                {
                    KEY_CODE: code,
                    "type": "key_hold",
                    CONF_DEVICE_DESCRIPTOR: self._descriptor,
                    CONF_DEVICE_NAME: dev.name,
                },
            )
            await asyncio.sleep(repeat)

    async def _async_monitor_input(self) -> None:
        """Monitor one device for key events using evdev with asyncio."""
        from evdev import categorize, ecodes  # noqa: PLC0415

        dev = self.dev
        assert dev is not None
        repeat_tasks: dict[int, asyncio.Task] = {}

        try:
            _LOGGER.debug("Start device monitoring")
            await self.hass.async_add_executor_job(dev.grab)
            async for event in dev.async_read_loop():
                if event.type == ecodes.EV_KEY:
                    if event.value in self._key_values:
                        _LOGGER.debug(
                            "device: %s: %s",
                            dev.name,
                            categorize(event),
                        )

                        self.hass.bus.async_fire(
                            EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED,
                            {
                                KEY_CODE: event.code,
                                "type": KEY_VALUE_NAME[event.value],
                                CONF_DEVICE_DESCRIPTOR: self._descriptor,
                                CONF_DEVICE_NAME: dev.name,
                            },
                        )

                    if event.value == KEY_VALUE["key_down"] and self._emulate_key_hold:
                        repeat_tasks[event.code] = self.hass.async_create_task(
                            self._async_keyrepeat(
                                dev,
                                event.code,
                                self._emulate_key_hold_delay,
                                self._emulate_key_hold_repeat,
                            )
                        )
                    elif (
                        event.value == KEY_VALUE["key_up"]
                        and event.code in repeat_tasks
                    ):
                        repeat_tasks[event.code].cancel()
                        del repeat_tasks[event.code]
        except asyncio.CancelledError:
            await self._async_cancel_repeats(repeat_tasks)
        except OSError as err:
            await self._async_cancel_repeats(repeat_tasks)
            _LOGGER.debug("Stopped reading %s: %s", dev.name, err)
            if self._on_monitor_failure is not None:
                await self._on_monitor_failure(self)

    async def _async_cancel_repeats(
        self, repeat_tasks: dict[int, asyncio.Task]
    ) -> None:
        """Cancel any outstanding emulated key hold tasks."""
        for task in repeat_tasks.values():
            task.cancel()

        if repeat_tasks:
            await asyncio.wait(repeat_tasks.values())
