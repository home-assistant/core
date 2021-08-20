"""The USB Discovery integration."""
from __future__ import annotations

import datetime
import logging
import sys

from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_usb

from .const import DOMAIN, FLOW_DISPATCHER, SEEN, USB
from .flow import FlowDispatcher, USBFlow
from .models import USBDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=5)


def _usb_device_from_port(port: ListPortInfo) -> USBDevice:
    return {
        "device": port.device,
        "vid": f"{hex(port.vid)[2:]:0>4}".upper(),
        "pid": f"{hex(port.pid)[2:]:0>4}".upper(),
        "serial_number": port.serial_number,
    }


@callback
def _async_process_discovered_usb_device(
    hass: HomeAssistant, device: USBDevice
) -> None:
    domain_data = hass.data[DOMAIN]
    seen = domain_data[SEEN]
    _LOGGER.debug("Discovered USB Device: %s", device)
    device_tuple = _usb_device_tuple(device)
    if device_tuple in seen:
        return
    seen.add(device_tuple)
    for matcher in domain_data[USB]:
        if "vid" in matcher and device["vid"] != matcher["vid"]:
            continue
        if "pid" in matcher and device["pid"] != matcher["pid"]:
            continue
        flow: USBFlow = {
            "domain": matcher["domain"],
            "context": {"source": config_entries.SOURCE_USB},
            "data": dict(device),
        }
        domain_data[FLOW_DISPATCHER].create(flow)


@callback
def _async_process_ports(hass: HomeAssistant, ports: list[ListPortInfo]) -> None:
    for port in ports:
        if port.vid is None and port.pid is None:
            continue
        _async_process_discovered_usb_device(hass, _usb_device_from_port(port))


def scan_serial(hass: HomeAssistant) -> None:
    """Scan serial ports."""
    hass.loop.call_soon_threadsafe(_async_process_ports, hass, comports())


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the USB Discovery integration."""
    flow_dispatcher = FlowDispatcher(hass)
    usb = await async_get_usb(hass)
    hass.data[DOMAIN] = {SEEN: set(), FLOW_DISPATCHER: flow_dispatcher, USB: usb}

    if not await _async_start_monitor(hass):
        await _async_start_scanner(hass)

    await hass.async_add_executor_job(scan_serial, hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, flow_dispatcher.async_start)

    return True


async def _async_start_scanner(hass: HomeAssistant) -> None:
    """Perodic scan with pyserial."""

    def _scan_serial():
        scan_serial(hass)

    stop_track = async_track_time_interval(hass, _scan_serial, SCAN_INTERVAL)

    @callback
    def _async_stop_scanner(*_):
        stop_track()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_scanner)


async def _async_start_monitor(hass: HomeAssistant) -> bool:
    """Start monitoring hardware with pyudev."""
    if not sys.platform.startswith("linux"):
        return False
    from pyudev import Context, Monitor, MonitorObserver

    try:
        context = Context()
    except ImportError:
        return False

    monitor = Monitor.from_netlink(context)
    monitor.filter_by(subsystem="tty")

    def _device_discovered(device):
        if device.action != "add":
            return
        _LOGGER.debug(
            "Discovered Device at path: %s, trigger scan",
            device.device_path,
        )
        scan_serial(hass)

    observer = MonitorObserver(
        monitor, callback=_device_discovered, name="usb-observer"
    )
    observer.start()

    async def _async_shutdown_observer(*_):
        await hass.async_add_executor_job(observer.stop)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_shutdown_observer)

    return True


def _usb_device_tuple(usb_device: USBDevice) -> tuple[str, str, str, str]:
    return (
        usb_device["device"],
        usb_device["vid"],
        usb_device["pid"],
        usb_device["serial_number"],
    )
