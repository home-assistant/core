"""Hub for communication with 1-Wire server or mount_dir."""
from __future__ import annotations

import os

from pi1wire import Pi1Wire
from pyownet import protocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_MOUNT_DIR, CONF_TYPE_OWSERVER, CONF_TYPE_SYSBUS
from .model import OWServerDeviceDescription

DEVICE_COUPLERS = {
    # Family : [branches]
    "1F": ["aux", "main"]
}


class OneWireHub:
    """Hub to communicate with SysBus or OWServer."""

    def __init__(self, hass: HomeAssistant):
        """Initialize."""
        self.hass = hass
        self.type: str | None = None
        self.pi1proxy: Pi1Wire | None = None
        self.owproxy: protocol._Proxy | None = None
        self.devices: list | None = None

    async def connect(self, host: str, port: int) -> None:
        """Connect to the owserver host."""
        try:
            self.owproxy = await self.hass.async_add_executor_job(
                protocol.proxy, host, port
            )
        except protocol.ConnError as exc:
            raise CannotConnect from exc

    async def check_mount_dir(self, mount_dir: str) -> None:
        """Test that the mount_dir is a valid path."""
        if not await self.hass.async_add_executor_job(os.path.isdir, mount_dir):
            raise InvalidPath
        self.pi1proxy = Pi1Wire(mount_dir)

    async def initialize(self, config_entry: ConfigEntry) -> None:
        """Initialize a config entry."""
        self.type = config_entry.data[CONF_TYPE]
        if self.type == CONF_TYPE_SYSBUS:
            await self.check_mount_dir(config_entry.data[CONF_MOUNT_DIR])
        elif self.type == CONF_TYPE_OWSERVER:
            host = config_entry.data[CONF_HOST]
            port = config_entry.data[CONF_PORT]
            await self.connect(host, port)
        await self.discover_devices()

    async def discover_devices(self) -> None:
        """Discover all devices."""
        if self.devices is None:
            if self.type == CONF_TYPE_SYSBUS:
                assert self.pi1proxy
                self.devices = await self.hass.async_add_executor_job(
                    self.pi1proxy.find_all_sensors
                )
            if self.type == CONF_TYPE_OWSERVER:
                self.devices = await self.hass.async_add_executor_job(
                    self._discover_devices_owserver
                )

    def _discover_devices_owserver(
        self, path: str = "/"
    ) -> list[OWServerDeviceDescription]:
        """Discover all owserver devices."""
        devices = []
        assert self.owproxy
        for device_path in self.owproxy.dir(path):
            device_family = self.owproxy.read(f"{device_path}family").decode()
            device_type = self.owproxy.read(f"{device_path}type").decode()
            device_branches = DEVICE_COUPLERS.get(device_family)
            if device_branches:
                for branch in device_branches:
                    devices += self._discover_devices_owserver(f"{device_path}{branch}")
            else:
                devices.append(
                    {
                        "path": device_path,
                        "family": device_family,
                        "type": device_type,
                    }
                )
        return devices


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidPath(HomeAssistantError):
    """Error to indicate the path is invalid."""
