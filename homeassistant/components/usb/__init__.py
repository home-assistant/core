"""The USB Discovery integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Sequence
import dataclasses
from datetime import datetime, timedelta
import fnmatch
from functools import partial
import logging
import os
import sys
from typing import Any, overload

from aiousbwatcher import AIOUSBWatcher, InotifyNotAvailableError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.helpers import config_validation as cv, discovery_flow
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.deprecation import (
    DeprecatedConstant,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service_info.usb import UsbServiceInfo as _UsbServiceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import USBMatcher, async_get_usb

from .const import DOMAIN
from .models import USBDevice
from .utils import (
    scan_serial_ports,
    usb_device_from_port,  # noqa: F401
)

_LOGGER = logging.getLogger(__name__)

PORT_EVENT_CALLBACK_TYPE = Callable[[set[USBDevice], set[USBDevice]], None]

POLLING_MONITOR_SCAN_PERIOD = timedelta(seconds=5)
REQUEST_SCAN_COOLDOWN = 10  # 10 second cooldown
ADD_REMOVE_SCAN_COOLDOWN = 5  # 5 second cooldown to give devices a chance to register

__all__ = [
    "USBCallbackMatcher",
    "async_is_plugged_in",
    "async_register_port_event_callback",
    "async_register_scan_request_callback",
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


class USBCallbackMatcher(USBMatcher):
    """Callback matcher for the USB integration."""


@hass_callback
def async_register_scan_request_callback(
    hass: HomeAssistant, callback: CALLBACK_TYPE
) -> CALLBACK_TYPE:
    """Register to receive a callback when a scan should be initiated."""
    discovery: USBDiscovery = hass.data[DOMAIN]
    return discovery.async_register_scan_request_callback(callback)


@hass_callback
def async_register_initial_scan_callback(
    hass: HomeAssistant, callback: CALLBACK_TYPE
) -> CALLBACK_TYPE:
    """Register to receive a callback when the initial USB scan is done.

    If the initial scan is already done, the callback is called immediately.
    """
    discovery: USBDiscovery = hass.data[DOMAIN]
    return discovery.async_register_initial_scan_callback(callback)


@hass_callback
def async_register_port_event_callback(
    hass: HomeAssistant, callback: PORT_EVENT_CALLBACK_TYPE
) -> CALLBACK_TYPE:
    """Register to receive a callback when a USB device is connected or disconnected."""
    discovery: USBDiscovery = hass.data[DOMAIN]
    return discovery.async_register_port_event_callback(callback)


@hass_callback
def async_is_plugged_in(hass: HomeAssistant, matcher: USBCallbackMatcher) -> bool:
    """Return True is a USB device is present."""

    vid = matcher.get("vid", "")
    pid = matcher.get("pid", "")
    serial_number = matcher.get("serial_number", "")
    manufacturer = matcher.get("manufacturer", "")
    description = matcher.get("description", "")

    if (
        vid != vid.upper()
        or pid != pid.upper()
        or serial_number != serial_number.lower()
        or manufacturer != manufacturer.lower()
        or description != description.lower()
    ):
        raise ValueError(
            f"vid and pid must be uppercase, the rest lowercase in matcher {matcher!r}"
        )

    usb_discovery: USBDiscovery = hass.data[DOMAIN]
    return any(
        _is_matching(
            USBDevice(
                device=device,
                vid=vid,
                pid=pid,
                serial_number=serial_number,
                manufacturer=manufacturer,
                description=description,
            ),
            matcher,
        )
        for (
            device,
            vid,
            pid,
            serial_number,
            manufacturer,
            description,
        ) in usb_discovery.seen
    )


_DEPRECATED_UsbServiceInfo = DeprecatedConstant(
    _UsbServiceInfo,
    "homeassistant.helpers.service_info.usb.UsbServiceInfo",
    "2026.2",
)


@overload
def human_readable_device_name(
    device: str,
    serial_number: str | None,
    manufacturer: str | None,
    description: str | None,
    vid: str | None,
    pid: str | None,
) -> str: ...


@overload
def human_readable_device_name(
    device: str,
    serial_number: str | None,
    manufacturer: str | None,
    description: str | None,
    vid: int | None,
    pid: int | None,
) -> str: ...


def human_readable_device_name(
    device: str,
    serial_number: str | None,
    manufacturer: str | None,
    description: str | None,
    vid: str | int | None,
    pid: str | int | None,
) -> str:
    """Return a human readable name from USBDevice attributes."""
    device_details = f"{device}, s/n: {serial_number or 'n/a'}"
    manufacturer_details = f" - {manufacturer}" if manufacturer else ""
    vendor_details = f" - {vid}:{pid}" if vid is not None else ""
    full_details = f"{device_details}{manufacturer_details}{vendor_details}"

    if not description:
        return full_details
    return f"{description[:26]} - {full_details}"


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path

    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the USB Discovery integration."""
    usb = await async_get_usb(hass)
    usb_discovery = USBDiscovery(hass, usb)
    await usb_discovery.async_setup()
    hass.data[DOMAIN] = usb_discovery
    websocket_api.async_register_command(hass, websocket_usb_scan)

    return True


def _fnmatch_lower(name: str | None, pattern: str) -> bool:
    """Match a lowercase version of the name."""
    if name is None:
        return False
    return fnmatch.fnmatch(name.lower(), pattern)


def _is_matching(device: USBDevice, matcher: USBMatcher | USBCallbackMatcher) -> bool:
    """Return True if a device matches."""
    if "vid" in matcher and device.vid != matcher["vid"]:
        return False
    if "pid" in matcher and device.pid != matcher["pid"]:
        return False
    if "serial_number" in matcher and not _fnmatch_lower(
        device.serial_number, matcher["serial_number"]
    ):
        return False
    if "manufacturer" in matcher and not _fnmatch_lower(
        device.manufacturer, matcher["manufacturer"]
    ):
        return False
    if "description" in matcher and not _fnmatch_lower(
        device.description, matcher["description"]
    ):
        return False
    return True


async def async_request_scan(hass: HomeAssistant) -> None:
    """Request a USB scan."""
    usb_discovery: USBDiscovery = hass.data[DOMAIN]
    if not usb_discovery.observer_active:
        await usb_discovery.async_request_scan()


class USBDiscovery:
    """Manage USB Discovery."""

    def __init__(
        self,
        hass: HomeAssistant,
        usb: list[USBMatcher],
    ) -> None:
        """Init USB Discovery."""
        self.hass = hass
        self.usb = usb
        self.seen: set[tuple[str, ...]] = set()
        self.observer_active = False
        self._request_debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None
        self._add_remove_debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None
        self._request_callbacks: list[CALLBACK_TYPE] = []
        self.initial_scan_done = False
        self._initial_scan_callbacks: list[CALLBACK_TYPE] = []
        self._port_event_callbacks: set[PORT_EVENT_CALLBACK_TYPE] = set()
        self._last_processed_devices: set[USBDevice] = set()
        self._scan_lock = asyncio.Lock()

    async def async_setup(self) -> None:
        """Set up USB Discovery."""
        try:
            await self._async_start_aiousbwatcher()
        except InotifyNotAvailableError as ex:
            _LOGGER.info(
                "Falling back to periodic filesystem polling for development, "
                "aiousbwatcher is not available on this system: %s",
                ex,
            )
            self._async_start_monitor_polling()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.async_start)
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)

    async def async_start(self, event: Event) -> None:
        """Start USB Discovery and run a manual scan."""
        await self._async_scan_serial()

    @hass_callback
    def async_stop(self, event: Event) -> None:
        """Stop USB Discovery."""
        if self._request_debouncer:
            self._request_debouncer.async_shutdown()

    @hass_callback
    def _async_start_monitor_polling(self) -> None:
        """Start monitoring hardware with polling (for development only!)."""

        async def _scan(event_time: datetime) -> None:
            await self._async_scan_serial()

        stop_callback = async_track_time_interval(
            self.hass, _scan, POLLING_MONITOR_SCAN_PERIOD
        )

        @hass_callback
        def _stop_polling(event: Event) -> None:
            stop_callback()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_polling)

    async def _async_start_aiousbwatcher(self) -> None:
        """Start monitoring hardware with aiousbwatcher.

        Returns True if successful.
        """

        @hass_callback
        def _usb_change_callback() -> None:
            self._async_delayed_add_remove_scan()

        watcher = AIOUSBWatcher()
        watcher.async_register_callback(_usb_change_callback)
        cancel = watcher.async_start()

        @hass_callback
        def _async_stop_watcher(event: Event) -> None:
            cancel()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_watcher)

        self.observer_active = True

    @hass_callback
    def async_register_scan_request_callback(
        self,
        _callback: CALLBACK_TYPE,
    ) -> CALLBACK_TYPE:
        """Register a scan request callback."""
        self._request_callbacks.append(_callback)

        @hass_callback
        def _async_remove_callback() -> None:
            self._request_callbacks.remove(_callback)

        return _async_remove_callback

    @hass_callback
    def async_register_initial_scan_callback(
        self,
        callback: CALLBACK_TYPE,
    ) -> CALLBACK_TYPE:
        """Register an initial scan callback."""
        if self.initial_scan_done:
            callback()
            return lambda: None

        self._initial_scan_callbacks.append(callback)

        @hass_callback
        def _async_remove_callback() -> None:
            if callback not in self._initial_scan_callbacks:
                return
            self._initial_scan_callbacks.remove(callback)

        return _async_remove_callback

    @hass_callback
    def async_register_port_event_callback(
        self,
        callback: PORT_EVENT_CALLBACK_TYPE,
    ) -> CALLBACK_TYPE:
        """Register a port event callback."""
        self._port_event_callbacks.add(callback)

        @hass_callback
        def _async_remove_callback() -> None:
            self._port_event_callbacks.discard(callback)

        return _async_remove_callback

    async def _async_process_discovered_usb_device(self, device: USBDevice) -> None:
        """Process a USB discovery."""
        _LOGGER.debug("Discovered USB Device: %s", device)
        device_tuple = dataclasses.astuple(device)
        if device_tuple in self.seen:
            return
        self.seen.add(device_tuple)

        matched = [matcher for matcher in self.usb if _is_matching(device, matcher)]
        if not matched:
            return

        service_info: _UsbServiceInfo | None = None

        sorted_by_most_targeted = sorted(matched, key=lambda item: -len(item))
        most_matched_fields = len(sorted_by_most_targeted[0])

        for matcher in sorted_by_most_targeted:
            # If there is a less targeted match, we only
            # want the most targeted match
            if len(matcher) < most_matched_fields:
                break

            if service_info is None:
                service_info = _UsbServiceInfo(
                    device=await self.hass.async_add_executor_job(
                        get_serial_by_id, device.device
                    ),
                    vid=device.vid,
                    pid=device.pid,
                    serial_number=device.serial_number,
                    manufacturer=device.manufacturer,
                    description=device.description,
                )

            discovery_flow.async_create_flow(
                self.hass,
                matcher["domain"],
                {"source": config_entries.SOURCE_USB},
                service_info,
            )

    async def _async_process_ports(self, usb_devices: Sequence[USBDevice]) -> None:
        """Process each discovered port."""
        _LOGGER.debug("USB devices: %r", usb_devices)

        # CP2102N chips create *two* serial ports on macOS: `/dev/cu.usbserial-` and
        # `/dev/cu.SLAB_USBtoUART*`. The former does not work and we should ignore them.
        if sys.platform == "darwin":
            silabs_serials = {
                dev.serial_number
                for dev in usb_devices
                if dev.device.startswith("/dev/cu.SLAB_USBtoUART")
            }

            filtered_usb_devices = {
                dev
                for dev in usb_devices
                if dev.serial_number not in silabs_serials
                or (
                    dev.serial_number in silabs_serials
                    and dev.device.startswith("/dev/cu.SLAB_USBtoUART")
                )
            }
        else:
            filtered_usb_devices = set(usb_devices)

        added_devices = filtered_usb_devices - self._last_processed_devices
        removed_devices = self._last_processed_devices - filtered_usb_devices
        self._last_processed_devices = filtered_usb_devices

        _LOGGER.debug(
            "Added devices: %r, removed devices: %r", added_devices, removed_devices
        )

        if added_devices or removed_devices:
            for callback in self._port_event_callbacks.copy():
                try:
                    callback(added_devices, removed_devices)
                except Exception:
                    _LOGGER.exception("Error in USB port event callback")

        for usb_device in filtered_usb_devices:
            await self._async_process_discovered_usb_device(usb_device)

    @hass_callback
    def _async_delayed_add_remove_scan(self) -> None:
        """Request a serial scan after a debouncer delay."""
        if not self._add_remove_debouncer:
            self._add_remove_debouncer = Debouncer(
                self.hass,
                _LOGGER,
                cooldown=ADD_REMOVE_SCAN_COOLDOWN,
                immediate=False,
                function=self._async_scan,
                background=True,
            )
        self._add_remove_debouncer.async_schedule_call()

    async def _async_scan_serial(self) -> None:
        """Scan serial ports."""
        _LOGGER.debug("Executing comports scan")
        async with self._scan_lock:
            await self._async_process_ports(
                await self.hass.async_add_executor_job(scan_serial_ports)
            )
        if self.initial_scan_done:
            return

        self.initial_scan_done = True
        while self._initial_scan_callbacks:
            self._initial_scan_callbacks.pop()()

    async def _async_scan(self) -> None:
        """Scan for USB devices and notify callbacks to scan as well."""
        for callback in self._request_callbacks:
            callback()
        await self._async_scan_serial()

    async def async_request_scan(self) -> None:
        """Request a serial scan."""
        if not self._request_debouncer:
            self._request_debouncer = Debouncer(
                self.hass,
                _LOGGER,
                cooldown=REQUEST_SCAN_COOLDOWN,
                immediate=True,
                function=self._async_scan,
                background=True,
            )
        await self._request_debouncer.async_call()


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "usb/scan"})
@websocket_api.async_response
async def websocket_usb_scan(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Scan for new usb devices."""
    await async_request_scan(hass)
    connection.send_result(msg["id"])


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
