"""Receive signals from a keyboard and use it as a remote control."""
# pylint: disable=import-error
import asyncio
from contextlib import suppress
import logging
import os

import aionotify
from evdev import InputDevice, categorize, ecodes, list_devices
import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEVICE_DESCRIPTOR = "device_descriptor"
DEVICE_ID_GROUP = "Device description"
DEVICE_NAME = "device_name"
DOMAIN = "keyboard_remote"

ICON = "mdi:remote"

KEY_CODE = "key_code"
KEY_VALUE = {"key_up": 0, "key_down": 1, "key_hold": 2}
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


async def async_setup(hass, config):
    """Set up the keyboard_remote."""
    config = config.get(DOMAIN)

    remote = KeyboardRemote(hass, config)
    remote.setup()

    return True


class KeyboardRemote:
    """Manage device connection/disconnection using inotify to asynchronously monitor."""

    def __init__(self, hass, config):
        """Create handlers and setup dictionaries to keep track of them."""
        self.hass = hass
        self.handlers_by_name = {}
        self.handlers_by_descriptor = {}
        self.active_handlers_by_descriptor = {}
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

        # start watching
        self.watcher = aionotify.Watcher()
        self.watcher.watch(
            alias="devinput",
            path=DEVINPUT,
            flags=aionotify.Flags.CREATE
            | aionotify.Flags.ATTRIB
            | aionotify.Flags.DELETE,
        )
        await self.watcher.setup(self.hass.loop)

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
            initial_start_monitoring.add(handler.async_start_monitoring(dev))

        if initial_start_monitoring:
            await asyncio.wait(initial_start_monitoring)

        self.monitor_task = self.hass.async_create_task(self.async_monitor_devices())

    async def async_stop_monitoring(self, event):
        """Stop and cleanup running monitoring tasks."""

        _LOGGER.debug("Cleanup on shutdown")

        if self.monitor_task is not None:
            if not self.monitor_task.done():
                self.monitor_task.cancel()
            await self.monitor_task

        handler_stop_monitoring = set()
        for handler in self.active_handlers_by_descriptor.values():
            handler_stop_monitoring.add(handler.async_stop_monitoring())

        if handler_stop_monitoring:
            await asyncio.wait(handler_stop_monitoring)

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

        try:
            while True:
                event = await self.watcher.get_event()
                descriptor = f"{DEVINPUT}/{event.name}"

                descriptor_active = descriptor in self.active_handlers_by_descriptor

                if (event.flags & aionotify.Flags.DELETE) and descriptor_active:
                    handler = self.active_handlers_by_descriptor[descriptor]
                    del self.active_handlers_by_descriptor[descriptor]
                    await handler.async_stop_monitoring()
                elif (
                    (event.flags & aionotify.Flags.CREATE)
                    or (event.flags & aionotify.Flags.ATTRIB)
                ) and not descriptor_active:
                    dev, handler = await self.hass.async_add_executor_job(
                        self.get_device_handler, descriptor
                    )
                    if handler is None:
                        continue
                    self.active_handlers_by_descriptor[descriptor] = handler
                    await handler.async_start_monitoring(dev)
        except asyncio.CancelledError:
            return

    class DeviceHandler:
        """Manage input events using evdev with asyncio."""

        def __init__(self, hass, dev_block):
            """Fill configuration data."""

            self.hass = hass

            key_types = dev_block.get(TYPE)

            self.key_values = set()
            for key_type in key_types:
                self.key_values.add(KEY_VALUE[key_type])

            self.emulate_key_hold = dev_block.get(EMULATE_KEY_HOLD)
            self.emulate_key_hold_delay = dev_block.get(EMULATE_KEY_HOLD_DELAY)
            self.emulate_key_hold_repeat = dev_block.get(EMULATE_KEY_HOLD_REPEAT)
            self.monitor_task = None
            self.dev = None

        async def async_keyrepeat(self, path, name, code, delay, repeat):
            """Emulate keyboard delay/repeat behaviour by sending key events on a timer."""

            await asyncio.sleep(delay)
            while True:
                self.hass.bus.async_fire(
                    KEYBOARD_REMOTE_COMMAND_RECEIVED,
                    {KEY_CODE: code, DEVICE_DESCRIPTOR: path, DEVICE_NAME: name},
                )
                await asyncio.sleep(repeat)

        async def async_start_monitoring(self, dev):
            """Start event monitoring task and issue event."""
            if self.monitor_task is None:
                self.dev = dev
                self.monitor_task = self.hass.async_create_task(
                    self.async_monitor_input(dev)
                )
                self.hass.bus.async_fire(
                    KEYBOARD_REMOTE_CONNECTED,
                    {DEVICE_DESCRIPTOR: dev.path, DEVICE_NAME: dev.name},
                )
                _LOGGER.debug("Keyboard (re-)connected, %s", dev.name)

        async def async_stop_monitoring(self):
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
                    {DEVICE_DESCRIPTOR: self.dev.path, DEVICE_NAME: self.dev.name},
                )
                _LOGGER.debug("Keyboard disconnected, %s", self.dev.name)
                self.dev = None

        async def async_monitor_input(self, dev):
            """Event monitoring loop.

            Monitor one device for new events using evdev with asyncio,
            start and stop key hold emulation tasks as needed.
            """

            repeat_tasks = {}

            try:
                _LOGGER.debug("Start device monitoring")
                await self.hass.async_add_executor_job(dev.grab)
                async for event in dev.async_read_loop():
                    if event.type is ecodes.EV_KEY:
                        if event.value in self.key_values:
                            _LOGGER.debug(categorize(event))
                            self.hass.bus.async_fire(
                                KEYBOARD_REMOTE_COMMAND_RECEIVED,
                                {
                                    KEY_CODE: event.code,
                                    DEVICE_DESCRIPTOR: dev.path,
                                    DEVICE_NAME: dev.name,
                                },
                            )

                        if (
                            event.value == KEY_VALUE["key_down"]
                            and self.emulate_key_hold
                        ):
                            repeat_tasks[event.code] = self.hass.async_create_task(
                                self.async_keyrepeat(
                                    dev.path,
                                    dev.name,
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
