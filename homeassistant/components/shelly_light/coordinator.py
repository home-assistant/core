"""Shelly Coordinator using mDNS and UDP discovery."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import socket
from typing import TypedDict

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
type ShellyConfigEntry = ConfigEntry[ShellyCoordinator]

UPDATE_INTERVAL = timedelta(seconds=30)


class ShellyDeviceInfo(TypedDict):
    """Type for Shelly device information."""

    device_id: str
    host: str
    port: int | None
    type: str
    model: str
    state: bool
    brightness: int | None
    online: bool


class ShellyDiscoveryListener(ServiceListener):
    """Listener for mDNS service discovery."""

    def __init__(self, coordinator: ShellyCoordinator) -> None:
        """Initialize the listener."""
        self.coordinator = coordinator

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Handle new service discovery."""
        info = zc.get_service_info(type_, name)
        if info and "shelly" in name.lower():
            ip_address = info.parsed_addresses()[0]
            device_id = name.split(".")[0]
            self.coordinator.add_device(
                {
                    "device_id": device_id,
                    "host": ip_address,
                    "port": info.port,
                    "type": "mdns",
                    "model": "Shelly",  # Default model, will be updated
                    "state": False,
                    "brightness": None,
                    "online": True,
                }
            )


class ShellyCoordinator(DataUpdateCoordinator[dict[str, ShellyDeviceInfo]]):
    """Coordinator for Shelly devices using custom discovery."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="Shelly Coordinator",
            update_interval=UPDATE_INTERVAL,
        )
        self.devices: dict[str, ShellyDeviceInfo] = {}
        self._zeroconf: Zeroconf | None = None
        self._udp_socket: socket.socket | None = None
        self._browser: ServiceBrowser | None = None
        self._listener: ShellyDiscoveryListener | None = None
        self._discovery_active = False
        self.added_devices: set[str] = set()

    async def start_discovery(self) -> None:
        """Start both mDNS and UDP discovery."""
        if self._discovery_active:
            return

        self._discovery_active = True

        # Start mDNS discovery
        self._zeroconf = Zeroconf()
        self._listener = ShellyDiscoveryListener(self)
        self._browser = ServiceBrowser(
            self._zeroconf,
            "_http._tcp.local.",
            self._listener,
        )

        # Start UDP discovery
        self._udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._udp_socket.bind(("", 5683))

        # Start discovery tasks
        self.hass.async_create_task(self._udp_discovery_task())
        self.hass.async_create_task(self._udp_listener_task())

    async def discover_devices(self) -> None:
        """Public method to start device discovery."""
        await self.start_discovery()

    async def shutdown(self) -> None:
        """Clean up resources."""
        if not self._discovery_active:
            return

        self._discovery_active = False

        if self._browser:
            self._browser.cancel()
            self._browser = None

        if self._zeroconf:
            self._zeroconf.close()
            self._zeroconf = None

        if self._udp_socket:
            self._udp_socket.close()
            self._udp_socket = None

    async def _udp_discovery_task(self) -> None:
        """Periodically send UDP discovery packets."""
        discovery_msg = bytes.fromhex("50010144b36369740173")
        while self._discovery_active and self._udp_socket:
            try:
                self._udp_socket.sendto(discovery_msg, ("224.0.0.251", 5683))
            except OSError as err:
                _LOGGER.error("UDP discovery error: %s", err)
            await asyncio.sleep(30)

    async def _udp_listener_task(self) -> None:
        """Listen for UDP responses."""
        while self._discovery_active and self._udp_socket:
            try:
                data, addr = await self.hass.async_add_executor_job(
                    self._udp_socket.recvfrom, 1024
                )
                self._process_udp_response(data, addr)
            except OSError as err:
                if self._discovery_active:
                    _LOGGER.debug("UDP listen error: %s", err)
                await asyncio.sleep(1)

    def _process_udp_response(self, data: bytes, addr: tuple) -> None:
        """Process UDP discovery response."""
        ip_address, port = addr
        if data.startswith(b"SHLY"):
            device_id = data[4:24].decode().strip("\x00")
            self.add_device(
                {
                    "device_id": device_id,
                    "host": ip_address,
                    "port": port,
                    "model": "shelly",
                    "type": "udp",
                    "state": False,
                    "brightness": None,
                    "online": True,
                }
            )

    def is_light_device(self, device_id: str) -> bool:
        """Basic check if device exists in registry."""  # noqa: D401

        return device_id in self.devices

    def add_device(self, device_info: ShellyDeviceInfo) -> None:
        """Add a discovered device."""
        if "port" not in device_info:
            _LOGGER.warning("Device missing port, using default 80")
            device_info["port"] = 80

        device_id = device_info["device_id"]
        if device_id not in self.devices:
            self.devices[device_id] = device_info
            _LOGGER.info("Discovered Shelly device: %s", device_id)
            self.async_set_updated_data(self.devices)
