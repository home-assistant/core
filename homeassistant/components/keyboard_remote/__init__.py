"""Receive signals from a keyboard and use it as a remote control."""
from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
import os
from typing import Any

from asyncinotify import Inotify, Mask
from evdev import InputDevice, categorize, ecodes, list_devices
import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DEVICE_DESCRIPTOR = "device_descriptor"
DEVICE_ID_GROUP = "Device description"
DEVICE_NAME = "device_name"
DOMAIN = "keyboard_remote"

ICON = "mdi:remote"

KEY_CODE = "key_code"
KEY_VALUE = {"key_up": 0, "key_down": 1, "key_hold": 2}
KEY_VALUE_NAME = {value: key for key, value in KEY_VALUE.items()}
KEYBOARD_REMOTE_COMMAND_RECEIVED = "keyboard_remote_command_received"
KEYBOARD_REMOTE_CONNECTED = "keyboard_remote_connected"
KEYBOARD_REMOTE_DISCONNECTED = "keyboard_remote_disconnected"

TYPE = "type"
EMULATE_KEY_HOLD = "emulate_key_hold"
EMULATE_KEY_HOLD_DELAY = "emulate_key_hold_delay"
EMULATE_KEY_HOLD_REPEAT = "emulate_key_hold_repeat"

DEVINPUT = "/dev/input"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Exclusive(DEVICE_DESCRIPTOR, DEVICE_ID_GROUP): cv.string,
                        vol.Exclusive(DEVICE_NAME, DEVICE_ID_GROUP): cv.string,
                        vol.Optional(TYPE, default=["key_up"]): vol.All(
                            cv.ensure_list, [vol.In(KEY_VALUE)]
                        ),
                        vol.Optional(EMULATE_KEY_HOLD, default=False): cv.boolean,
                        vol.Optional(EMULATE_KEY_HOLD_DELAY, default=0.250): float,
                        vol.Optional(EMULATE_KEY_HOLD_REPEAT, default=0.033): float,
                    }
                ),
                cv.has_at_least_one_key(DEVICE_DESCRIPTOR, DEVICE_ID_GROUP),
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the keyboard_remote."""
    domain_config: list[dict[str, Any]] = config[DOMAIN]

    remote = KeyboardRemote(hass, domain_config)
    remote.setup()

    return True


class KeyboardRemote:
    """Manage device connection/disconnection using inotify to asynchronously monitor."""

    def __init__(self, hass: HomeAssistant, config: list[dict[str, Any]]) -> None:
        """Create handlers and setup dictionaries to keep track of them."""
        self.hass = hass
        self.handlers_by_name = {}
        self.handlers_by_descriptor = {}
        self.active_handlers_by_descriptor: dict[str, asyncio.Future] = {}
        self.inotify = None
        self.watcher = None
        self.monitor_task = None

        for dev_block in config:
            handler = self.DeviceHandler(hass, dev_block)
            descriptor = dev_block.get(DEVICE_DESCRIPTOR)
            if descriptor is not None:
                self.handlers_by_descriptor[descriptor] = handler
            else:
                name = dev_block.get(DEVICE_NAME)
                self.handlers_by_name[name] = handler

    def setup(self):
        """Listen for Home Assistant start and stop events."""

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self.async_start_monitoring
        )
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.async_stop_monitoring
        )

    async def async_start_monitoring(self, event):
        """Start monitoring of events and devices.

        Start inotify watching for events, start event monitoring for those already
        connected, and start monitoring for device connection/disconnection.
        """

        _LOGGER.debug("Start monitoring")

        self.inotify = Inotify()
        self.watcher = self.inotify.add_watch(
            DEVINPUT, Mask.CREATE | Mask.ATTRIB | Mask.DELETE
        )

        # add initial devices (do this AFTER starting watcher in order to
        # avoid race conditions leading to missing device connections)
        initial_start_monitoring = set()
        descriptors = await self.hass.async_add_executor_job(list_devices, DEVINPUT)
        for descriptor in descriptors:
            dev, handler = await self.hass.async_add_executor_job(
                self.get_device_handler, descriptor
            )

            if handler is None:
                continue

            self.active_handlers_by_descriptor[descriptor] = handler
            initial_start_monitoring.add(
                asyncio.create_task(handler.async_device_start_monitoring(dev))
            )

        if initial_start_monitoring:
            await asyncio.wait(initial_start_monitoring)

        self.monitor_task = self.hass.async_create_task(self.async_monitor_devices())

    async def async_stop_monitoring(self, event):
        """Stop and cleanup running monitoring tasks."""

        _LOGGER.debug("Cleanup on shutdown")

        if self.inotify and self.watcher:
            self.inotify.rm_watch(self.watcher)
            self.watcher = None

        if self.monitor_task is not None:
            if not self.monitor_task.done():
                self.monitor_task.cancel()
            await self.monitor_task

        handler_stop_monitoring = set()
        for handler in self.active_handlers_by_descriptor.values():
            handler_stop_monitoring.add(
                asyncio.create_task(handler.async_device_stop_monitoring())
            )
        if handler_stop_monitoring:
            await asyncio.wait(handler_stop_monitoring)

        if self.inotify:
            self.inotify.close()
            self.inotify = None

    def get_device_handler(self, descriptor):
        """Find the correct device handler given a descriptor (path)."""

        # devices are often added and then correct permissions set after
        try:
            dev = InputDevice(descriptor)
        except OSError:
            return (None, None)

        handler = None
        if descriptor in self.handlers_by_descriptor:
            handler = self.handlers_by_descriptor[descriptor]
        elif dev.name in self.handlers_by_name:
            handler = self.handlers_by_name[dev.name]
        else:
            # check for symlinked paths matching descriptor
            for test_descriptor, test_handler in self.handlers_by_descriptor.items():
                if test_handler.dev is not None:
                    fullpath = test_handler.dev.path
                else:
                    fullpath = os.path.realpath(test_descriptor)
                if fullpath == descriptor:
                    handler = test_handler

        return (dev, handler)

    async def async_monitor_devices(self):
        """Monitor asynchronously for device connection/disconnection or permissions changes."""

        _LOGGER.debug("Start monitoring loop")

        try:
            async for event in self.inotify:
                descriptor = f"{DEVINPUT}/{event.name}"
                _LOGGER.debug(
                    "got event for %s: %s",
                    descriptor,
                    event.mask,
                )

                descriptor_active = descriptor in self.active_handlers_by_descriptor

                if (event.mask & Mask.DELETE) and descriptor_active:
                    _LOGGER.debug("removing: %s", descriptor)
                    handler = self.active_handlers_by_descriptor[descriptor]
                    del self.active_handlers_by_descriptor[descriptor]
                    await handler.async_device_stop_monitoring()
                elif (
                    (event.mask & Mask.CREATE) or (event.mask & Mask.ATTRIB)
                ) and not descriptor_active:
                    _LOGGER.debug("checking new: %s", descriptor)
                    dev, handler = await self.hass.async_add_executor_job(
                        self.get_device_handler, descriptor
                    )
                    if handler is None:
                        continue
                    _LOGGER.debug("adding: %s", descriptor)
                    self.active_handlers_by_descriptor[descriptor] = handler
                    await handler.async_device_start_monitoring(dev)
        except asyncio.CancelledError:
            _LOGGER.debug("Monitoring canceled")
            return

    class DeviceHandler:
        """Manage input events using evdev with asyncio."""

        def __init__(self, hass: HomeAssistant, dev_block: dict[str, Any]) -> None:
            """Fill configuration data."""

            self.hass = hass

            key_types = dev_block[TYPE]

            self.key_values = set()
            for key_type in key_types:
                self.key_values.add(KEY_VALUE[key_type])

            self.emulate_key_hold = dev_block[EMULATE_KEY_HOLD]
            self.emulate_key_hold_delay = dev_block[EMULATE_KEY_HOLD_DELAY]
            self.emulate_key_hold_repeat = dev_block[EMULATE_KEY_HOLD_REPEAT]
            self.monitor_task = None
            self.dev = None
            self.config_descriptor = dev_block.get(DEVICE_DESCRIPTOR)
            self.descriptor = None

        async def async_device_keyrepeat(self, code, delay, repeat):
            """Emulate keyboard delay/repeat behaviour by sending key events on a timer."""

            await asyncio.sleep(delay)
            while True:
                self.hass.bus.async_fire(
                    KEYBOARD_REMOTE_COMMAND_RECEIVED,
                    {
                        KEY_CODE: code,
                        TYPE: "key_hold",
                        DEVICE_DESCRIPTOR: self.descriptor,
                        DEVICE_NAME: self.dev.name,
                    },
                )
                await asyncio.sleep(repeat)

        async def async_device_start_monitoring(self, dev):
            """Start event monitoring task and issue event."""
            _LOGGER.debug("Keyboard async_device_start_monitoring, %s", dev.name)
            if self.monitor_task is None:
                self.dev = dev
                # set the descriptor to the one provided to the config if any, falling back to the device path if not set
                if self.config_descriptor:
                    self.descriptor = self.config_descriptor
                else:
                    self.descriptor = self.dev.path

                self.monitor_task = self.hass.async_create_task(
                    self.async_device_monitor_input()
                )
                self.hass.bus.async_fire(
                    KEYBOARD_REMOTE_CONNECTED,
                    {
                        DEVICE_DESCRIPTOR: self.descriptor,
                        DEVICE_NAME: dev.name,
                    },
                )
                _LOGGER.debug("Keyboard (re-)connected, %s", dev.name)

        async def async_device_stop_monitoring(self):
            """Stop event monitoring task and issue event."""
            if self.monitor_task is not None:
                with suppress(OSError):
                    await self.hass.async_add_executor_job(self.dev.ungrab)
                # monitoring of the device form the event loop and closing of the
                # device has to occur before cancelling the task to avoid
                # triggering unhandled exceptions inside evdev coroutines
                asyncio.get_event_loop().remove_reader(self.dev.fileno())
                self.dev.close()
                if not self.monitor_task.done():
                    self.monitor_task.cancel()
                await self.monitor_task
                self.monitor_task = None
                self.hass.bus.async_fire(
                    KEYBOARD_REMOTE_DISCONNECTED,
                    {
                        DEVICE_DESCRIPTOR: self.descriptor,
                        DEVICE_NAME: self.dev.name,
                    },
                )
                _LOGGER.debug("Keyboard disconnected, %s", self.dev.name)
                self.dev = None
                self.descriptor = self.config_descriptor

        async def async_device_monitor_input(self):
            """Event monitoring loop.

            Monitor one device for new events using evdev with asyncio,
            start and stop key hold emulation tasks as needed.
            """

            repeat_tasks = {}

            try:
                _LOGGER.debug("Start device monitoring")
                await self.hass.async_add_executor_job(self.dev.grab)
                async for event in self.dev.async_read_loop():
                    if event.type is ecodes.EV_KEY:
                        if event.value in self.key_values:
                            _LOGGER.debug(
                                "device: %s: %s", self.dev.name, categorize(event)
                            )

                            self.hass.bus.async_fire(
                                KEYBOARD_REMOTE_COMMAND_RECEIVED,
                                {
                                    KEY_CODE: event.code,
                                    TYPE: KEY_VALUE_NAME[event.value],
                                    DEVICE_DESCRIPTOR: self.descriptor,
                                    DEVICE_NAME: self.dev.name,
                                },
                            )

                        if (
                            event.value == KEY_VALUE["key_down"]
                            and self.emulate_key_hold
                        ):
                            repeat_tasks[event.code] = self.hass.async_create_task(
                                self.async_device_keyrepeat(
                                    event.code,
                                    self.emulate_key_hold_delay,
                                    self.emulate_key_hold_repeat,
                                )
                            )
                        elif (
                            event.value == KEY_VALUE["key_up"]
                            and event.code in repeat_tasks
                        ):
                            repeat_tasks[event.code].cancel()
                            del repeat_tasks[event.code]
            except (OSError, asyncio.CancelledError):
                # cancel key repeat tasks
                for task in repeat_tasks.values():
                    task.cancel()

                if repeat_tasks:
                    await asyncio.wait(repeat_tasks.values())
