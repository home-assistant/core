"""Receive signals from a keyboard and use it as a remote control."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
import os
from typing import TYPE_CHECKING, Any

from asyncinotify import Inotify, Mask
import voluptuous as vol

if TYPE_CHECKING:
    from evdev import InputDevice

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType

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
)

_LOGGER = logging.getLogger(__name__)

# Legacy YAML constants (used only for CONFIG_SCHEMA parsing)
_DEVICE_DESCRIPTOR = "device_descriptor"
_DEVICE_ID_GROUP = "Device description"
_DEVICE_NAME = "device_name"
_TYPE = "type"
_EMULATE_KEY_HOLD = "emulate_key_hold"
_EMULATE_KEY_HOLD_DELAY = "emulate_key_hold_delay"
_EMULATE_KEY_HOLD_REPEAT = "emulate_key_hold_repeat"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Exclusive(_DEVICE_DESCRIPTOR, _DEVICE_ID_GROUP): cv.string,
                        vol.Exclusive(_DEVICE_NAME, _DEVICE_ID_GROUP): cv.string,
                        vol.Optional(_TYPE, default=["key_up"]): vol.All(
                            cv.ensure_list, [vol.In(KEY_VALUE)]
                        ),
                        vol.Optional(_EMULATE_KEY_HOLD, default=False): cv.boolean,
                        vol.Optional(_EMULATE_KEY_HOLD_DELAY, default=0.250): float,
                        vol.Optional(_EMULATE_KEY_HOLD_REPEAT, default=0.033): float,
                    }
                ),
                cv.has_at_least_one_key(_DEVICE_DESCRIPTOR, _DEVICE_NAME),
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
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
        and result.get("reason") != "already_configured"
    ):
        reason = result.get("reason", "unknown")
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{reason}",
            breaks_in_ha_version="2026.9.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{reason}",
            translation_placeholders={
                "url": "/config/integrations/dashboard/add?domain=keyboard_remote"
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2026.9.0",
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
    if DOMAIN not in hass.data:
        manager = KeyboardRemoteManager(hass)
        hass.data[DOMAIN] = manager
    else:
        manager = hass.data[DOMAIN]

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
    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    await manager.unregister_handler(entry.entry_id)

    # If this was the last loaded entry, tear down the shared manager
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        await manager.async_stop()
        hass.data.pop(DOMAIN, None)

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
        self._started = False

    async def async_start(self) -> None:
        """Start the inotify watcher (idempotent, lock-protected)."""
        async with self._lock:
            if self._started:
                return

            _LOGGER.debug("Start monitoring")

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

    async def async_stop(self) -> None:
        """Stop the inotify watcher and all device handlers."""
        async with self._lock:
            if not self._started:
                return

            _LOGGER.debug("Cleanup on shutdown")

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
                asyncio.create_task(handler.async_device_stop_monitoring())
                for handler in self._active_handlers_by_descriptor.values()
            }
            if stop_tasks:
                await asyncio.wait(stop_tasks)
            self._active_handlers_by_descriptor.clear()

            if self._inotify:
                self._inotify.close()
                self._inotify = None

            self._started = False

    def register_handler(self, entry_id: str, handler: DeviceHandler) -> None:
        """Register a DeviceHandler for a config entry."""
        self._handlers[entry_id] = handler
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
        """Find the matching handler for a device descriptor (path).

        The handlers list must be a snapshot taken on the event loop thread
        to avoid race conditions with register/unregister.
        """
        from evdev import InputDevice  # noqa: PLC0415

        # Devices are often added and then correct permissions set after
        try:
            dev = InputDevice(descriptor)
        except OSError:
            return (None, None)

        for handler in handlers:
            if handler.matches_device(descriptor, dev):
                return (dev, handler)

        dev.close()
        return (None, None)

    async def _async_scan_initial_devices(self) -> None:
        """Scan all current /dev/input/ devices and start matching handlers."""
        from evdev import list_devices  # noqa: PLC0415

        start_tasks: set[asyncio.Task] = set()
        handlers = list(self._handlers.values())
        descriptors = await self.hass.async_add_executor_job(list_devices, DEVINPUT)
        for descriptor in descriptors:
            dev, handler = await self.hass.async_add_executor_job(
                self._get_handler_for_device, descriptor, handlers
            )

            if handler is None or dev is None:
                continue

            self._active_handlers_by_descriptor[descriptor] = handler
            start_tasks.add(
                asyncio.create_task(handler.async_device_start_monitoring(dev))
            )

        if start_tasks:
            await asyncio.wait(start_tasks)

    async def _async_check_handler(self, handler: DeviceHandler) -> None:
        """Check if a newly registered handler's device is currently connected."""
        from evdev import list_devices  # noqa: PLC0415

        handlers = list(self._handlers.values())
        descriptors = await self.hass.async_add_executor_job(list_devices, DEVINPUT)
        for descriptor in descriptors:
            if descriptor in self._active_handlers_by_descriptor:
                continue
            dev, matched = await self.hass.async_add_executor_job(
                self._get_handler_for_device, descriptor, handlers
            )
            if matched is handler and dev is not None:
                self._active_handlers_by_descriptor[descriptor] = handler
                await handler.async_device_start_monitoring(dev)
                return

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
                    _LOGGER.debug("adding: %s", descriptor)
                    self._active_handlers_by_descriptor[descriptor] = handler
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

    @property
    def _device_path(self) -> str:
        """The configured device path (by-id or raw)."""
        return self.entry.data[CONF_DEVICE_PATH]

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

    def matches_device(self, descriptor: str, dev: InputDevice) -> bool:
        """Check if this handler matches the given device.

        Matching order:
        1. By-id device_path realpath comparison
        2. Original YAML descriptor realpath comparison
        3. Device name match
        """
        real_path = os.path.realpath(descriptor)

        # Check by-id or configured path
        device_path = self._device_path
        if device_path and os.path.exists(device_path):
            if os.path.realpath(device_path) == real_path:
                return True

        # Check original YAML descriptor
        yaml_descriptor = self._device_descriptor
        if yaml_descriptor:
            if os.path.realpath(yaml_descriptor) == real_path:
                return True

        # Check by device name
        if self._device_name_config and dev.name == self._device_name_config:
            return True

        return False

    async def async_device_start_monitoring(self, dev: InputDevice) -> None:
        """Start event monitoring task and fire connected event."""
        _LOGGER.debug("Keyboard async_device_start_monitoring, %s", dev.name)
        if self._monitor_task is not None:
            return

        self.dev = dev
        # Use the configured path for event data, falling back to device path
        self._descriptor = self._device_path or self.dev.path

        self._monitor_task = self.hass.async_create_task(self._async_monitor_input())
        self.hass.bus.async_fire(
            EVENT_KEYBOARD_REMOTE_CONNECTED,
            {
                CONF_DEVICE_DESCRIPTOR: self._descriptor,
                CONF_DEVICE_NAME: dev.name,
            },
        )
        _LOGGER.debug("Keyboard (re-)connected, %s", dev.name)

    async def async_device_stop_monitoring(self) -> None:
        """Stop event monitoring task and fire disconnected event."""
        if self._monitor_task is None:
            return

        dev = self.dev
        assert dev is not None

        with suppress(OSError):
            await self.hass.async_add_executor_job(dev.ungrab)
        # Remove reader and close device before cancelling the task to avoid
        # triggering unhandled exceptions inside evdev coroutines
        self.hass.loop.remove_reader(dev.fileno())
        dev.close()
        if not self._monitor_task.done():
            self._monitor_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._monitor_task
        self._monitor_task = None
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
        except OSError, asyncio.CancelledError:
            # Cancel key repeat tasks
            for task in repeat_tasks.values():
                task.cancel()

            if repeat_tasks:
                await asyncio.wait(repeat_tasks.values())
