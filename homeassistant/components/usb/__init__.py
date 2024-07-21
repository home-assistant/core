"""The USB Discovery integration."""

from __future__ import annotations

from collections.abc import Coroutine
import dataclasses
import fnmatch
import logging
import os
import sys
from typing import TYPE_CHECKING, Any

from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)
from homeassistant.data_entry_flow import BaseServiceInfo
from homeassistant.helpers import config_validation as cv, discovery_flow, system_info
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import USBMatcher, async_get_usb

from .const import DOMAIN
from .models import USBDevice
from .utils import usb_device_from_port

if TYPE_CHECKING:
    from pyudev import Device, MonitorObserver

_LOGGER = logging.getLogger(__name__)

REQUEST_SCAN_COOLDOWN = 60  # 1 minute cooldown

__all__ = [
    "async_is_plugged_in",
    "async_register_scan_request_callback",
    "USBCallbackMatcher",
    "UsbServiceInfo",
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
        _is_matching(USBDevice(*device_tuple), matcher)
        for device_tuple in usb_discovery.seen
    )


@dataclasses.dataclass(slots=True)
class UsbServiceInfo(BaseServiceInfo):
    """Prepared info from usb entries."""

    device: str
    vid: str
    pid: str
    serial_number: str | None
    manufacturer: str | None
    description: str | None


def human_readable_device_name(
    device: str,
    serial_number: str | None,
    manufacturer: str | None,
    description: str | None,
    vid: str | None,
    pid: str | None,
) -> str:
    """Return a human readable name from USBDevice attributes."""
    device_details = f"{device}, s/n: {serial_number or 'n/a'}"
    manufacturer_details = f" - {manufacturer}" if manufacturer else ""
    vendor_details = f" - {vid}:{pid}" if vid else ""
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
        self._request_callbacks: list[CALLBACK_TYPE] = []
        self.initial_scan_done = False
        self._initial_scan_callbacks: list[CALLBACK_TYPE] = []

    async def async_setup(self) -> None:
        """Set up USB Discovery."""
        await self._async_start_monitor()
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

    async def _async_start_monitor(self) -> None:
        """Start monitoring hardware with pyudev."""
        if not sys.platform.startswith("linux"):
            return
        info = await system_info.async_get_system_info(self.hass)
        if info.get("docker"):
            return

        if not (
            observer := await self.hass.async_add_executor_job(
                self._get_monitor_observer
            )
        ):
            return

        def _stop_observer(event: Event) -> None:
            observer.stop()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_observer)
        self.observer_active = True

    def _get_monitor_observer(self) -> MonitorObserver | None:
        """Get the monitor observer.

        This runs in the executor because the import
        does blocking I/O.
        """
        from pyudev import (  # pylint: disable=import-outside-toplevel
            Context,
            Monitor,
            MonitorObserver,
        )

        try:
            context = Context()
        except (ImportError, OSError):
            return None

        monitor = Monitor.from_netlink(context)
        try:
            monitor.filter_by(subsystem="tty")
        except ValueError as ex:  # this fails on WSL
            _LOGGER.debug(
                "Unable to setup pyudev filtering; This is expected on WSL: %s", ex
            )
            return None

        observer = MonitorObserver(
            monitor, callback=self._device_discovered, name="usb-observer"
        )

        observer.start()
        return observer

    def _device_discovered(self, device: Device) -> None:
        """Call when the observer discovers a new usb tty device."""
        if device.action != "add":
            return
        _LOGGER.debug(
            "Discovered Device at path: %s, triggering scan serial",
            device.device_path,
        )
        self.hass.create_task(self._async_scan())

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

        service_info: UsbServiceInfo | None = None

        sorted_by_most_targeted = sorted(matched, key=lambda item: -len(item))
        most_matched_fields = len(sorted_by_most_targeted[0])

        for matcher in sorted_by_most_targeted:
            # If there is a less targeted match, we only
            # want the most targeted match
            if len(matcher) < most_matched_fields:
                break

            if service_info is None:
                service_info = UsbServiceInfo(
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

    async def _async_process_ports(self, ports: list[ListPortInfo]) -> None:
        """Process each discovered port."""
        usb_devices = [
            usb_device_from_port(port)
            for port in ports
            if port.vid is not None or port.pid is not None
        ]

        # CP2102N chips create *two* serial ports on macOS: `/dev/cu.usbserial-` and
        # `/dev/cu.SLAB_USBtoUART*`. The former does not work and we should ignore them.
        if sys.platform == "darwin":
            silabs_serials = {
                dev.serial_number
                for dev in usb_devices
                if dev.device.startswith("/dev/cu.SLAB_USBtoUART")
            }

            usb_devices = [
                dev
                for dev in usb_devices
                if dev.serial_number not in silabs_serials
                or (
                    dev.serial_number in silabs_serials
                    and dev.device.startswith("/dev/cu.SLAB_USBtoUART")
                )
            ]

        for usb_device in usb_devices:
            await self._async_process_discovered_usb_device(usb_device)

    async def _async_scan_serial(self) -> None:
        """Scan serial ports."""
        await self._async_process_ports(
            await self.hass.async_add_executor_job(comports)
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
    usb_discovery: USBDiscovery = hass.data[DOMAIN]
    if not usb_discovery.observer_active:
        await usb_discovery.async_request_scan()
    connection.send_result(msg["id"])
