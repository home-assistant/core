"""The USB Discovery integration."""
from __future__ import annotations

import datetime
import logging
import sys

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SEEN
from .models import USBDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=5)


@callback
def _async_process_discovered_usb_device(
    hass: HomeAssistant, device: USBDevice
) -> None:
    domain_data = hass.data[DOMAIN]
    seen = domain_data[SEEN]

    device_tuple = _usb_device_tuple(device)
    if device_tuple in seen:
        return
    seen.add(device_tuple)
    _LOGGER.warning("Discovered USB Device: %s", device_tuple)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the USB Discovery integration."""
    hass.data[DOMAIN] = {SEEN: {}}

    if await _async_start_monitor(hass):
        return True
    await _async_start_scanner(hass)
    return True


async def _async_start_scanner(hass: HomeAssistant) -> None:
    """Perodic scan with pyserial."""
    from serial.tools.list_ports import comports
    from serial.tools.list_ports_common import ListPortInfo

    def _usb_device_from_port(port: ListPortInfo) -> USBDevice:
        return {
            "device": port.device,
            "vid": port.vid,
            "pid": port.pid,
            "serial_number": port.serial_number,
        }

    @callback
    def _async_process_ports(ports):
        for port in ports:
            _async_process_discovered_usb_device(hass, _usb_device_from_port(port))

    def _scan_serial(*_):
        hass.loop.call_soon_threadsafe(_async_process_ports, comports())

    stop_track = async_track_time_interval(hass, _scan_serial, SCAN_INTERVAL)

    @callback
    def _async_stop_scanner(*_):
        stop_track()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_scanner)
    await hass.async_add_executor_job(_scan_serial)


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
        _LOGGER.debug("Discovered Device: %s", device)

    observer = MonitorObserver(
        monitor, callback=_device_discovered, name="usb-observer"
    )
    observer.start()

    async def _async_shutdown_observer(*_):
        await hass.async_add_executor_job(observer.stop)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_shutdown_observer)

    return True


def _usb_device_tuple(usb_device: USBDevice) -> tuple[str, int, int, str]:
    return (
        usb_device["device"],
        usb_device["vid"],
        usb_device["pid"],
        usb_device["serial_number"],
    )
