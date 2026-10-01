"""Receive signals from a keyboard and use it as a remote control."""

import asyncio
from collections.abc import Callable, Coroutine
from contextlib import suppress
import logging
import os
from typing import TYPE_CHECKING, Any

from asyncinotify import Event as InotifyEvent, Inotify, Mask, Watch
import probatio

if TYPE_CHECKING:
    from evdev import InputDevice

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_TYPE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    DOMAIN as HOMEASSISTANT_DOMAIN,
    Event,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_DEVICE_DESCRIPTOR,
    CONF_DEVICE_NAME,
    CONF_DEVICE_PATH,
    CONF_DEVICE_UNIQ,
    CONF_EMULATE_KEY_HOLD,
    CONF_EMULATE_KEY_HOLD_DELAY,
    CONF_EMULATE_KEY_HOLD_REPEAT,
    CONF_KEY_TYPES,
    DEFAULT_EMULATE_KEY_HOLD,
    DEFAULT_EMULATE_KEY_HOLD_DELAY,
    DEFAULT_EMULATE_KEY_HOLD_REPEAT,
    DEFAULT_KEY_TYPES,
    DEVINPUT,
    DEVINPUT_BY_ID,
    DOMAIN,
    EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED,
    EVENT_KEYBOARD_REMOTE_CONNECTED,
    EVENT_KEYBOARD_REMOTE_DISCONNECTED,
    KEY_CODE,
    KEY_VALUE,
    KEY_VALUE_NAME,
    MATCH_DEVICE_NAME,
    MATCH_DEVICE_PATH,
    MATCH_DEVICE_UNIQ,
)

_LOGGER = logging.getLogger(__name__)


def _list_by_id_links() -> list[str]:
    """List the names in /dev/input/by-id, if it exists (runs in executor)."""
    with suppress(OSError), os.scandir(DEVINPUT_BY_ID) as entries:
        return sorted(entry.name for entry in entries)
    return []


def list_input_devices() -> list[str]:
    """List the event nodes in /dev/input (runs in executor).

    evdev checks each node after listing the directory, which raises if a node
    is removed in between. List again then, as the node is simply gone.
    """
    from evdev import list_devices  # noqa: PLC0415

    for _ in range(3):
        with suppress(FileNotFoundError):
            return list_devices(DEVINPUT)
    return []


DATA_MANAGER: HassKey[KeyboardRemoteManager] = HassKey(DOMAIN)

_DEVICE_ID_GROUP = "Device description"

# Lenient apart from what makes a block unusable, as an invalid config would
# keep every entry of the integration from loading. The import fits the
# values into what the options accept.
CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.All(
            probatio.EnsureList(),
            [
                # All, not a list: a list accepts a block that passes any one
                # of its validators, so an invalid block would pass unchanged.
                probatio.All(
                    probatio.AtLeastOne(CONF_DEVICE_DESCRIPTOR, CONF_DEVICE_NAME),
                    probatio.Schema(
                        {
                            probatio.Exclusive(
                                CONF_DEVICE_DESCRIPTOR, _DEVICE_ID_GROUP
                            ): probatio.All(cv.string, probatio.Length(min=1)),
                            probatio.Exclusive(
                                CONF_DEVICE_NAME, _DEVICE_ID_GROUP
                            ): probatio.All(cv.string, probatio.Length(min=1)),
                            probatio.Optional(
                                CONF_TYPE, default=DEFAULT_KEY_TYPES
                            ): probatio.All(
                                probatio.EnsureList(), [probatio.In(KEY_VALUE)]
                            ),
                            probatio.Optional(
                                CONF_EMULATE_KEY_HOLD, default=DEFAULT_EMULATE_KEY_HOLD
                            ): cv.boolean,
                            probatio.Optional(
                                CONF_EMULATE_KEY_HOLD_DELAY,
                                default=DEFAULT_EMULATE_KEY_HOLD_DELAY,
                            ): probatio.Coerce(float),
                            probatio.Optional(
                                CONF_EMULATE_KEY_HOLD_REPEAT,
                                default=DEFAULT_EMULATE_KEY_HOLD_REPEAT,
                            ): probatio.Coerce(float),
                        },
                        extra=probatio.ALLOW_EXTRA,
                    ),
                )
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
    """Import a single YAML device block and flag YAML as deprecated."""
    # The schema guarantees a usable block, so the import creates an entry or
    # finds the one it created before
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=dev_block,
    )
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


type KeyboardRemoteConfigEntry = ConfigEntry[DeviceHandler]


async def async_setup_entry(
    hass: HomeAssistant, entry: KeyboardRemoteConfigEntry
) -> bool:
    """Set up a single keyboard remote device from a config entry."""
    if (manager := hass.data.get(DATA_MANAGER)) is None:
        manager = KeyboardRemoteManager(hass)
        # Open the watcher now rather than at start, so a failure fails setup
        # and Home Assistant retries it instead of leaving the entry inactive.
        try:
            manager.open_watcher()
        except OSError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_watch_input",
                # The error names the path that failed
                translation_placeholders={"error": str(err)},
            ) from err
        hass.data[DATA_MANAGER] = manager

    entry.runtime_data = DeviceHandler(hass, entry)
    manager.register_handler(entry.runtime_data)

    async def _async_start(_: HomeAssistant) -> None:
        await manager.async_start()

    entry.async_on_unload(async_at_start(hass, _async_start))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: KeyboardRemoteConfigEntry
) -> bool:
    """Unload a keyboard remote config entry."""
    manager = hass.data[DATA_MANAGER]
    await manager.unregister_handler(entry.runtime_data)

    if not hass.config_entries.async_loaded_entries(DOMAIN):
        # Detach it before awaiting, so an entry that sets up meanwhile creates
        # a new manager instead of registering with this stopping one.
        hass.data.pop(DATA_MANAGER, None)
        await manager.async_stop()

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
        self._watcher: Watch | None = None
        self._by_id_watcher: Watch | None = None
        self._monitor_task: asyncio.Task[None] | None = None
        self._stop_listener: CALLBACK_TYPE | None = None
        self._started = False
        # Cleared as soon as stopping begins, unlike _started, so device checks
        # still in flight cannot claim a device after the handlers were stopped.
        self._accepting_devices = False

    def open_watcher(self) -> None:
        """Create the inotify watches, closing everything again on failure.

        Raises OSError when /dev/input cannot be watched, for example in a
        container without it mapped, or once the inotify instance limit is hit.
        A by-id watch that fails is only logged and retried on later events,
        as devices without a by-id link do not need it.
        """
        try:
            self._inotify = Inotify()
            self._watcher = self._inotify.add_watch(
                DEVINPUT, Mask.CREATE | Mask.ATTRIB | Mask.DELETE
            )
        except OSError:
            if self._inotify is not None:
                self._inotify.close()
                self._inotify = None
            raise
        try:
            self._watch_by_id()
        except OSError as err:
            _LOGGER.warning("Unable to watch %s: %s", DEVINPUT_BY_ID, err)

    async def async_start(self) -> None:
        """Scan for devices and start monitoring (idempotent, lock-protected)."""
        async with self._lock:
            # A stopped manager has closed its watcher and is not restarted
            if self._started or self._inotify is None:
                return

            _LOGGER.debug("Start monitoring")
            self._accepting_devices = True

            # Config entries are not unloaded when Home Assistant stops, so
            # without this the devices are never ungrabbed on shutdown.
            self._stop_listener = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._async_handle_hass_stop
            )

            # Scan initial devices AFTER starting watcher to avoid race
            # conditions leading to missing device connections
            scanned = await self._async_scan_initial_devices()

            self._monitor_task = self.hass.async_create_background_task(
                self._async_monitor_devices(), "keyboard_remote device watcher"
            )
            self._started = True

            # Entries that loaded while the scan ran were not part of it, and
            # register_handler skipped them because the manager had not started.
            for handler in self._handlers.values():
                if handler not in scanned:
                    self.hass.async_create_task(self._async_check_handler(handler))

    def _watch_by_id(self) -> None:
        """Watch the by-id directory for new symlinks.

        udev creates the by-id symlink after the event node and its permission
        changes, so a handler configured with a by-id path cannot match on the
        node's own events. systemd-udevd renames each link into place, so the
        final name arrives as MOVED_TO rather than CREATE.
        """
        assert self._inotify is not None
        # udev creates the directory with the first link and removes it with
        # the last one, so a missing directory is expected.
        with suppress(FileNotFoundError):
            self._by_id_watcher = self._inotify.add_watch(
                DEVINPUT_BY_ID, Mask.CREATE | Mask.MOVED_TO
            )

    async def _async_handle_hass_stop(self, event: Event) -> None:
        """Tear down when Home Assistant stops."""
        self._stop_listener = None
        await self.async_stop()

    async def async_stop(self) -> None:
        """Stop the inotify watcher and all device handlers."""
        async with self._lock:
            # The watcher opens at setup, so an entry unloaded before Home
            # Assistant started still has one to close.
            if not self._started and self._inotify is None:
                return

            _LOGGER.debug("Cleanup on shutdown")
            self._accepting_devices = False

            if self._stop_listener is not None:
                self._stop_listener()
                self._stop_listener = None

            if self._inotify and self._watcher:
                # Fails if /dev/input went away and the kernel dropped the
                # watch, which must not stop the devices from being released.
                with suppress(OSError):
                    self._inotify.rm_watch(self._watcher)
                self._watcher = None
            if self._inotify and self._by_id_watcher:
                # Fails if udev removed the directory before its IGNORED
                # event was read.
                with suppress(OSError):
                    self._inotify.rm_watch(self._by_id_watcher)
                self._by_id_watcher = None

            if (monitor_task := self._monitor_task) is not None:
                self._monitor_task = None
                monitor_task.cancel()
                # Unlike awaiting the task, this neither raises its error nor
                # swallows a cancellation of this stop
                await asyncio.wait({monitor_task})
                if not monitor_task.cancelled() and (err := monitor_task.exception()):
                    # Log it and still release the devices below
                    _LOGGER.error(
                        "The input device watcher had failed",
                        exc_info=(type(err), err, err.__traceback__),
                    )

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
        self._forget_handler(handler)
        await handler.async_device_stop_monitoring(from_monitor_task=True)

    def register_handler(self, handler: DeviceHandler) -> None:
        """Register a config entry's DeviceHandler."""
        self._handlers[handler.entry.entry_id] = handler
        handler.set_monitor_failure_callback(self._async_release_failed_handler)
        if self._started:
            self.hass.async_create_task(self._async_check_handler(handler))

    async def unregister_handler(self, handler: DeviceHandler) -> None:
        """Unregister a DeviceHandler and stop its monitoring."""
        del self._handlers[handler.entry.entry_id]
        self._forget_handler(handler)
        await handler.async_device_stop_monitoring()

    def _forget_handler(self, handler: DeviceHandler) -> None:
        """Drop the nodes mapped to a handler."""
        for descriptor in [
            descriptor
            for descriptor, active in self._active_handlers_by_descriptor.items()
            if active is handler
        ]:
            del self._active_handlers_by_descriptor[descriptor]

    def _get_handler_for_device(
        self, descriptor: str, handlers: list[DeviceHandler]
    ) -> tuple[InputDevice, DeviceHandler, int] | None:
        """Find the best matching handler for a device descriptor, and its rank.

        The handlers list must be a snapshot taken on the event loop thread
        to avoid race conditions with register/unregister.
        """
        from evdev import InputDevice  # noqa: PLC0415

        # Devices are often added and then correct permissions set after
        try:
            dev = InputDevice(descriptor)
        except OSError:
            return None

        best: tuple[DeviceHandler, int] | None = None
        for handler in handlers:
            rank = handler.match_rank(descriptor, dev)
            if rank is None:
                continue
            if best is None or rank < best[1]:
                best = handler, rank

        if best is None:
            dev.close()
            return None

        return dev, *best

    def _scan_and_match_devices(
        self, handlers: list[DeviceHandler]
    ) -> list[tuple[str, InputDevice, DeviceHandler]]:
        """List all devices and give each handler its strongest match.

        Every candidate is ranked before anything is assigned. Matching device
        by device instead would let a name match on one node of a composite
        keyboard claim the handler before its exact device_path match is
        reached, and list_devices() returns nodes in arbitrary order.
        """
        from evdev import InputDevice  # noqa: PLC0415

        opened: dict[str, InputDevice] = {}
        candidates: list[tuple[int, str, DeviceHandler]] = []
        for descriptor in list_input_devices():
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

    async def _async_scan_initial_devices(self) -> list[DeviceHandler]:
        """Scan all current /dev/input/ devices and start matching handlers.

        Returns the handlers the scan considered.
        """
        handlers = list(self._handlers.values())
        matches = await self.hass.async_add_executor_job(
            self._scan_and_match_devices, handlers
        )

        for descriptor, dev, handler in matches:
            if self._claim_descriptor(descriptor, dev, handler):
                handler.async_device_start_monitoring(dev)
        return handlers

    def _find_device_for_handler(
        self,
        handler: DeviceHandler,
        handlers: list[DeviceHandler],
        skip_descriptors: set[str],
    ) -> tuple[str, InputDevice] | None:
        """Find a connected device matching a handler (runs in executor).

        Every device a handler matches gets the same rank from it, so the first
        one that no other handler matches better will do.
        """
        for descriptor in sorted(list_input_devices()):
            if descriptor in skip_descriptors:
                continue
            if (found := self._get_handler_for_device(descriptor, handlers)) is None:
                continue
            dev, matched, _rank = found
            if matched is handler:
                return descriptor, dev
            dev.close()
        return None

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
            not self._can_take_device(handler)
            or descriptor in self._active_handlers_by_descriptor
        ):
            self.hass.async_add_executor_job(dev.close)
            return False

        self._active_handlers_by_descriptor[descriptor] = handler
        return True

    @callback
    def _can_take_device(self, handler: DeviceHandler) -> bool:
        """Return whether a handler is registered and free for a device."""
        return (
            self._accepting_devices
            and self._handlers.get(handler.entry.entry_id) is handler
            and not handler.is_monitoring
        )

    async def _async_check_handler(self, handler: DeviceHandler) -> None:
        """Check if a newly registered handler's device is currently connected."""
        handlers = list(self._handlers.values())
        skip = set(self._active_handlers_by_descriptor)
        result = await self.hass.async_add_executor_job(
            self._find_device_for_handler, handler, handlers, skip
        )
        if result is not None:
            self._claim_and_start(*result, handler)

    async def _async_monitor_devices(self) -> None:
        """Monitor /dev/input/ for device add/remove events via inotify."""
        _LOGGER.debug("Start monitoring loop")

        assert self._inotify is not None
        try:
            async for event in self._inotify:
                try:
                    await self._async_handle_inotify_event(event)
                except Exception:
                    # Ending the loop would stop every device from connecting
                    _LOGGER.exception("Error handling input device event %s", event)
        except asyncio.CancelledError:
            _LOGGER.debug("Monitoring canceled")
            return

    async def _async_handle_inotify_event(self, event: InotifyEvent) -> None:
        """Handle one event from /dev/input or /dev/input/by-id."""
        if self._by_id_watcher is not None and event.watch is self._by_id_watcher:
            await self._async_handle_by_id_event(event)
            return

        if Mask.Q_OVERFLOW in event.mask:
            # Removed devices fail their reads and release themselves, but
            # added ones would go unnoticed
            _LOGGER.warning("Missed input device events, checking all devices")
            await self._async_handle_unseen_links()
            return

        # Events on /dev/input itself name no node
        if event.name is None:
            return

        if str(event.name) == "by-id":
            if Mask.CREATE in event.mask:
                await self._async_handle_by_id_created()
            return

        # A device plugged in now gets its by-id link after this event, and
        # that link is only seen with the watch in place.
        if self._by_id_watcher is None:
            await self._async_retry_by_id_watch()

        descriptor = f"{DEVINPUT}/{event.name}"
        _LOGGER.debug("Event for %s: %s", descriptor, event.mask)

        descriptor_active = descriptor in self._active_handlers_by_descriptor

        if (event.mask & Mask.DELETE) and descriptor_active:
            _LOGGER.debug("Removing %s", descriptor)
            handler = self._active_handlers_by_descriptor[descriptor]
            del self._active_handlers_by_descriptor[descriptor]
            await handler.async_device_stop_monitoring()
        elif (
            (event.mask & Mask.CREATE) or (event.mask & Mask.ATTRIB)
        ) and not descriptor_active:
            _LOGGER.debug("Checking new %s", descriptor)
            await self._async_attach_descriptor(descriptor)

    async def _async_attach_descriptor(self, descriptor: str) -> None:
        """Start the best matching handler on a device node, if any."""
        handlers = list(self._handlers.values())
        found = await self.hass.async_add_executor_job(
            self._get_handler_for_device, descriptor, handlers
        )
        if found is not None:
            dev, handler, _rank = found
            self._claim_and_start(descriptor, dev, handler)

    @callback
    def _claim_and_start(
        self, descriptor: str, dev: InputDevice, handler: DeviceHandler
    ) -> None:
        """Start monitoring a matched device, unless the claim is refused."""
        if self._claim_descriptor(descriptor, dev, handler):
            _LOGGER.debug("Adding %s", descriptor)
            handler.async_device_start_monitoring(dev)

    def _match_linked_device(
        self,
        link: str,
        handlers: list[DeviceHandler],
        holders: dict[str, DeviceHandler],
    ) -> tuple[str, InputDevice, DeviceHandler] | None:
        """Find the handler for the node a by-id link points to (executor).

        A node that already has a handler is only returned when the link makes
        a stronger match for another one.
        """
        descriptor = os.path.realpath(link)
        # by-id also links mouse and joystick nodes, which evdev cannot open
        if not descriptor.startswith(f"{DEVINPUT}/event"):
            return None
        if (found := self._get_handler_for_device(descriptor, handlers)) is None:
            return None
        dev, handler, rank = found
        if (holder := holders.get(descriptor)) is not None:
            holder_rank = holder.match_rank(descriptor, dev)
            if holder is handler or (holder_rank is not None and holder_rank <= rank):
                dev.close()
                return None
        return descriptor, dev, handler

    async def _async_handle_by_id_event(self, event: InotifyEvent) -> None:
        """Handle a new by-id symlink by checking the node it points to."""
        if Mask.IGNORED in event.mask:
            # The directory was removed along with its last link
            self._by_id_watcher = None
            return
        if event.name is None or not event.mask & (Mask.CREATE | Mask.MOVED_TO):
            return
        await self._async_handle_link(str(event.name))

    async def _async_handle_link(self, name: str) -> None:
        """Start, or hand over, the node that a by-id link points to."""
        _LOGGER.debug("Checking by-id link %s", name)
        holders = dict(self._active_handlers_by_descriptor)
        result = await self.hass.async_add_executor_job(
            self._match_linked_device,
            f"{DEVINPUT_BY_ID}/{name}",
            list(self._handlers.values()),
            holders,
        )
        if result is None:
            return
        descriptor, dev, handler = result
        holder = holders.get(descriptor)
        if (
            holder is not None
            and self._active_handlers_by_descriptor.get(descriptor) is holder
            and self._can_take_device(handler)
        ):
            # The holder got the node from its node events, before this link
            # let the entry configured with it match. Hand the node over, then
            # let the holder look for another node.
            _LOGGER.debug("Handing %s over for its by-id link", descriptor)
            del self._active_handlers_by_descriptor[descriptor]
            await holder.async_device_stop_monitoring()
            self._claim_and_start(descriptor, dev, handler)
            await self._async_check_handler(holder)
            return
        self._claim_and_start(descriptor, dev, handler)

    async def _async_handle_by_id_created(self) -> None:
        """Start watching a by-id directory that udev just created."""
        if self._by_id_watcher is not None:
            return
        try:
            self._watch_by_id()
        except OSError as err:
            # Raising here would end the monitor loop. The watch is retried
            # on later /dev/input events.
            _LOGGER.warning("Unable to watch %s: %s", DEVINPUT_BY_ID, err)
        await self._async_handle_unseen_links()

    async def _async_retry_by_id_watch(self) -> None:
        """Watch the by-id directory after an earlier attempt failed."""
        try:
            self._watch_by_id()
        except OSError as err:
            _LOGGER.debug("Still unable to watch %s: %s", DEVINPUT_BY_ID, err)
            return
        if self._by_id_watcher is not None:
            await self._async_handle_unseen_links()

    async def _async_handle_unseen_links(self) -> None:
        """Handle the by-id links whose events were missed.

        Handle each as a new link, then check the handlers still waiting for a
        device, which also finds nodes without a link.
        """
        for name in await self.hass.async_add_executor_job(_list_by_id_links):
            await self._async_handle_link(name)
        for handler in list(self._handlers.values()):
            if not handler.is_monitoring:
                await self._async_check_handler(handler)


class DeviceHandler:
    """Manage input events for a single keyboard device (one config entry)."""

    def __init__(self, hass: HomeAssistant, entry: KeyboardRemoteConfigEntry) -> None:
        """Initialize from config entry data and options."""
        self.hass = hass
        self.entry = entry
        self._monitor_task: asyncio.Task[None] | None = None
        self.dev: InputDevice | None = None
        self._descriptor: str | None = None
        self._repeat_tasks: dict[int, asyncio.Task[None]] = {}
        self._on_monitor_failure: (
            Callable[[DeviceHandler], Coroutine[Any, Any, None]] | None
        ) = None
        # The options flow reloads the entry, so these cannot change while
        # this handler exists.
        options = entry.options
        self._key_values = {KEY_VALUE[key_type] for key_type in options[CONF_KEY_TYPES]}
        self._emulate_key_hold: bool = options[CONF_EMULATE_KEY_HOLD]
        self._emulate_key_hold_delay: float = options[CONF_EMULATE_KEY_HOLD_DELAY]
        self._emulate_key_hold_repeat: float = options[CONF_EMULATE_KEY_HOLD_REPEAT]

    def set_monitor_failure_callback(
        self, on_failure: Callable[[DeviceHandler], Coroutine[Any, Any, None]]
    ) -> None:
        """Set what the manager should run if this device stops being readable."""
        self._on_monitor_failure = on_failure

    @property
    def is_monitoring(self) -> bool:
        """Whether this handler already has a device to read from."""
        return self._monitor_task is not None

    @property
    def _device_path(self) -> str | None:
        """The configured device path, if the entry has one.

        Entries matched by name, or by uniq and name, store none, as the only
        path they could store is a /dev/input/eventN that can change.
        """
        return self.entry.data.get(CONF_DEVICE_PATH)

    @property
    def _device_uniq(self) -> str | None:
        """The configured evdev uniq, for devices added without a by-id link."""
        return self.entry.data.get(CONF_DEVICE_UNIQ)

    @property
    def _device_name(self) -> str | None:
        """The configured device name."""
        return self.entry.data.get(CONF_DEVICE_NAME)

    @property
    def _device_descriptor(self) -> str | None:
        """The original YAML device_descriptor, if any."""
        return self.entry.data.get(CONF_DEVICE_DESCRIPTOR)

    def match_rank(self, descriptor: str, dev: InputDevice) -> int | None:
        """Return how strongly this handler matches a device, or None.

        Lower ranks are stronger, and callers must prefer the strongest match
        rather than the first one they find. A composite keyboard reports the
        same name on every node it exposes, so a name match alone cannot tell
        the node the user selected from its siblings.
        """
        real_path = os.path.realpath(descriptor)

        # An imported YAML descriptor is stored here too, or replaced by the
        # by-id link it resolved to. Matching the raw descriptor on its own
        # would bind whatever device reuses that eventN while the link is gone.
        device_path = self._device_path
        if (
            device_path
            and os.path.exists(device_path)
            and os.path.realpath(device_path) == real_path
        ):
            return MATCH_DEVICE_PATH

        # Check by device name, but only for entries that have nothing better.
        # An entry configured with a path keeps that identity even while the
        # node is missing, because a composite keyboard reports the same name
        # on every node it exposes and a sibling would be the wrong device.
        if (
            not device_path
            and not self._device_descriptor
            and self._device_name
            and dev.name == self._device_name
        ):
            # The uniq tells identical Bluetooth remotes apart
            if uniq := self._device_uniq:
                return MATCH_DEVICE_UNIQ if dev.uniq == uniq else None
            return MATCH_DEVICE_NAME

        return None

    @callback
    def async_device_start_monitoring(self, dev: InputDevice) -> None:
        """Start event monitoring task and fire connected event."""
        _LOGGER.debug("Starting monitoring of %s", dev.name)
        self.dev = dev
        # Events carry the path the entry was set up from, so automations
        # written against a YAML setup keep matching: the YAML descriptor, or
        # for a YAML entry configured by name the node that was opened, even
        # when the import also resolved a by-id path.
        if self._device_descriptor:
            self._descriptor = self._device_descriptor
        elif self.entry.source == SOURCE_IMPORT:
            self._descriptor = dev.path
        else:
            self._descriptor = self._device_path or dev.path

        # Created here, not by the task: a teardown before its first step
        # must still cancel the repeats it starts
        self._repeat_tasks = {}
        # Not eager: a device that fails immediately would otherwise run the
        # whole monitor body, including the teardown that clears this
        # attribute, before the assignment below overwrites it again.
        self._monitor_task = self.hass.async_create_background_task(
            self._async_monitor_input(self._repeat_tasks),
            f"keyboard_remote monitor {dev.path}",
            eager_start=False,
        )
        self.hass.bus.async_fire(
            EVENT_KEYBOARD_REMOTE_CONNECTED,
            {
                CONF_DEVICE_DESCRIPTOR: self._descriptor,
                CONF_DEVICE_NAME: dev.name,
            },
        )
        _LOGGER.debug("Connected %s", dev.name)

    async def async_device_stop_monitoring(
        self, *, from_monitor_task: bool = False
    ) -> None:
        """Stop event monitoring task and fire disconnected event.

        Pass from_monitor_task=True when the monitor task itself is tearing
        down after a read failure. It cannot wait for its own completion, and
        ungrabbing a device that just errored would only raise again.
        """
        if (task := self._monitor_task) is None:
            return

        dev = self.dev
        assert dev is not None
        descriptor = self._descriptor
        repeat_tasks = self._repeat_tasks

        # Claim the teardown before the first await. On unplug the DELETE event
        # and the monitor task's read failure both land here, and a second pass
        # would call remove_reader on the fd the first one already closed.
        self._monitor_task = None

        try:
            if not from_monitor_task:
                with suppress(OSError):
                    await self.hass.async_add_executor_job(dev.ungrab)
        finally:
            # Also when this teardown is cancelled, so the device is released.
            # Remove the reader before closing to avoid unhandled exceptions
            # inside evdev coroutines, and close in the executor, as closing
            # an input device can block.
            self.hass.loop.remove_reader(dev.fileno())
            self.hass.async_add_executor_job(dev.close)
            if not from_monitor_task:
                task.cancel()
            # The monitor task only cancels these once it runs again, which
            # would let a key_hold follow the disconnect
            for repeat_task in repeat_tasks.values():
                repeat_task.cancel()
            self.hass.bus.async_fire(
                EVENT_KEYBOARD_REMOTE_DISCONNECTED,
                {
                    CONF_DEVICE_DESCRIPTOR: descriptor,
                    CONF_DEVICE_NAME: dev.name,
                },
            )
            _LOGGER.debug("Disconnected %s", dev.name)
            # A device check may have started this handler on another node
            # while the old one ungrabbed
            if self.dev is dev:
                self.dev = None
        if not from_monitor_task:
            # Unlike awaiting the task, this cannot swallow a cancellation of
            # the caller, which would keep a stopping watcher running
            await asyncio.wait({task})

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

    async def _async_monitor_input(
        self, repeat_tasks: dict[int, asyncio.Task[None]]
    ) -> None:
        """Monitor one device for key events using evdev with asyncio."""
        from evdev import ecodes  # noqa: PLC0415

        dev = self.dev
        assert dev is not None

        try:
            _LOGGER.debug("Start device monitoring")
            try:
                await self.hass.async_add_executor_job(dev.grab)
            except OSError as err:
                _LOGGER.warning(
                    "Unable to grab %s, it may be in use by another program: %s",
                    dev.name,
                    err,
                )
                raise
            async for event in dev.async_read_loop():
                if event.type == ecodes.EV_KEY:
                    if event.value in self._key_values:
                        # Not evdev's categorize, which raises for key codes
                        # missing from its table
                        _LOGGER.debug(
                            "Key %s %s on %s",
                            event.code,
                            KEY_VALUE_NAME[event.value],
                            dev.name,
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
                        # A key_up lost while the loop stalled would otherwise
                        # leave the previous repeat running forever
                        if previous := repeat_tasks.pop(event.code, None):
                            previous.cancel()
                        repeat_tasks[event.code] = (
                            self.hass.async_create_background_task(
                                self._async_keyrepeat(
                                    dev,
                                    event.code,
                                    self._emulate_key_hold_delay,
                                    self._emulate_key_hold_repeat,
                                ),
                                f"keyboard_remote key repeat {event.code}",
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
            _LOGGER.debug("Stopped reading %s: %s", dev.name, err)
            await self._async_monitor_failed(repeat_tasks)
        except Exception:
            # Anything else would end the task with the device still grabbed
            # and the handler looking busy, so release it the same way.
            _LOGGER.exception("Unexpected error reading %s", dev.name)
            await self._async_monitor_failed(repeat_tasks)

    async def _async_monitor_failed(
        self, repeat_tasks: dict[int, asyncio.Task[None]]
    ) -> None:
        """Release this handler's device after its monitor stopped reading."""
        await self._async_cancel_repeats(repeat_tasks)
        if self._on_monitor_failure is not None:
            await self._on_monitor_failure(self)

    async def _async_cancel_repeats(
        self, repeat_tasks: dict[int, asyncio.Task[None]]
    ) -> None:
        """Cancel any outstanding emulated key hold tasks."""
        for task in repeat_tasks.values():
            task.cancel()

        if repeat_tasks:
            await asyncio.wait(repeat_tasks.values())
