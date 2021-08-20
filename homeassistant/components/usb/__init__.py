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

from .flow import FlowDispatcher, USBFlow
from .models import USBDevice
from .utils import USBDeviceTupleType, usb_device_from_port, usb_device_tuple

_LOGGER = logging.getLogger(__name__)

# Scanning only happens on non-linux systems
SCAN_INTERVAL = datetime.timedelta(minutes=60)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the USB Discovery integration."""
    usb = await async_get_usb(hass)
    usb_discovery = USBDiscovery(hass, FlowDispatcher(hass), usb)
    await usb_discovery.async_setup()
    return True


class USBDiscovery:
    """Manage USB Discovery."""

    def __init__(
        self,
        hass: HomeAssistant,
        flow_dispatcher: FlowDispatcher,
        usb: list[dict[str, str]],
    ) -> None:
        """Init USB Discovery."""
        self.hass = hass
        self.flow_dispatcher = flow_dispatcher
        self.usb = usb
        self.seen: set[USBDeviceTupleType] = set()

    async def async_setup(self):
        """Set up USB Discovery."""
        if not await self._async_start_monitor():
            await self._async_start_scanner()
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self.async_start)

    async def async_start(self):
        """Start USB Discovery and run a manual scan."""
        self.flow_dispatcher.async_start()
        await self.hass.async_add_executor_job(self.scan_serial)

    async def _async_start_scanner(self) -> None:
        """Perodic scan with pyserial when the observer is not available."""
        stop_track = async_track_time_interval(
            self.hass, lambda now: self.scan_serial(), SCAN_INTERVAL
        )
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, callback(lambda event: stop_track())
        )

    async def _async_start_monitor(self) -> bool:
        """Start monitoring hardware with pyudev."""
        if not sys.platform.startswith("linux"):
            return False
        from pyudev import (  # pylint: disable=import-outside-toplevel
            Context,
            Monitor,
            MonitorObserver,
        )

        try:
            context = Context()
        except ImportError:
            return False

        monitor = Monitor.from_netlink(context)
        monitor.filter_by(subsystem="tty")
        observer = MonitorObserver(
            monitor, callback=self._device_discovered, name="usb-observer"
        )
        observer.start()
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, lambda event: observer.stop()
        )
        return True

    def _device_discovered(self, device):
        """Call when the observer discovers a new usb tty device."""
        if device.action != "add":
            return
        _LOGGER.debug(
            "Discovered Device at path: %s, triggering scan serial",
            device.device_path,
        )
        self.scan_serial()

    @callback
    def _async_process_discovered_usb_device(self, device: USBDevice) -> None:
        """Process a USB discovery."""
        _LOGGER.debug("Discovered USB Device: %s", device)
        device_tuple = usb_device_tuple(device)
        if device_tuple in self.seen:
            return
        self.seen.add(device_tuple)
        for matcher in self.usb:
            if "vid" in matcher and device["vid"] != matcher["vid"]:
                continue
            if "pid" in matcher and device["pid"] != matcher["pid"]:
                continue
            flow: USBFlow = {
                "domain": matcher["domain"],
                "context": {"source": config_entries.SOURCE_USB},
                "data": dict(device),
            }
            self.flow_dispatcher.create(flow)

    @callback
    def _async_process_ports(self, ports: list[ListPortInfo]) -> None:
        """Process each discovered port."""
        for port in ports:
            if port.vid is None and port.pid is None:
                continue
            self._async_process_discovered_usb_device(usb_device_from_port(port))

    def scan_serial(self) -> None:
        """Scan serial ports."""
        self.hass.loop.call_soon_threadsafe(self._async_process_ports, comports())
