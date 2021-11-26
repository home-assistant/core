"""Hub for communication with 1-Wire server or mount_dir."""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from pi1wire import Pi1Wire
from pyownet import protocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_VIA_DEVICE,
    CONF_HOST,
    CONF_PORT,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    CONF_MOUNT_DIR,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEVICE_SUPPORT_OWSERVER,
    DEVICE_SUPPORT_SYSBUS,
    DOMAIN,
    MANUFACTURER_EDS,
    MANUFACTURER_HOBBYBOARDS,
    MANUFACTURER_MAXIM,
)
from .model import (
    OWDeviceDescription,
    OWDirectDeviceDescription,
    OWServerDeviceDescription,
)

DEVICE_COUPLERS = {
    # Family : [branches]
    "1F": ["aux", "main"]
}

DEVICE_MANUFACTURER = {
    "7E": MANUFACTURER_EDS,
    "EF": MANUFACTURER_HOBBYBOARDS,
}

_LOGGER = logging.getLogger(__name__)


def _is_known_owserver_device(device_family: str, device_type: str) -> bool:
    """Check if device family/type is known to the library."""
    if device_family in ("7E", "EF"):  # EDS or HobbyBoard
        return device_type in DEVICE_SUPPORT_OWSERVER[device_family]
    return device_family in DEVICE_SUPPORT_OWSERVER


class OneWireHub:
    """Hub to communicate with SysBus or OWServer."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        self.type: str | None = None
        self.pi1proxy: Pi1Wire | None = None
        self.owproxy: protocol._Proxy | None = None
        self.devices: list[OWDeviceDescription] | None = None

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
            mount_dir = config_entry.data[CONF_MOUNT_DIR]
            _LOGGER.debug("Initializing using SysBus %s", mount_dir)
            await self.check_mount_dir(mount_dir)
        elif self.type == CONF_TYPE_OWSERVER:
            host = config_entry.data[CONF_HOST]
            port = config_entry.data[CONF_PORT]
            _LOGGER.debug("Initializing using OWServer %s:%s", host, port)
            await self.connect(host, port)
        await self.discover_devices()
        if TYPE_CHECKING:
            assert self.devices
        # Register discovered devices on Hub
        device_registry = dr.async_get(self.hass)
        for device in self.devices:
            device_info: DeviceInfo = device.device_info
            device_registry.async_get_or_create(
                config_entry_id=config_entry.entry_id,
                identifiers=device_info[ATTR_IDENTIFIERS],
                manufacturer=device_info[ATTR_MANUFACTURER],
                model=device_info[ATTR_MODEL],
                name=device_info[ATTR_NAME],
                via_device=device_info.get(ATTR_VIA_DEVICE),
            )

    async def discover_devices(self) -> None:
        """Discover all devices."""
        if self.devices is None:
            if self.type == CONF_TYPE_SYSBUS:
                self.devices = await self.hass.async_add_executor_job(
                    self._discover_devices_sysbus
                )
            if self.type == CONF_TYPE_OWSERVER:
                self.devices = await self.hass.async_add_executor_job(
                    self._discover_devices_owserver
                )

    def _discover_devices_sysbus(self) -> list[OWDeviceDescription]:
        """Discover all sysbus devices."""
        devices: list[OWDeviceDescription] = []
        assert self.pi1proxy
        all_sensors = self.pi1proxy.find_all_sensors()
        if not all_sensors:
            _LOGGER.error(
                "No onewire sensor found. Check if dtoverlay=w1-gpio "
                "is in your /boot/config.txt. "
                "Check the mount_dir parameter if it's defined"
            )
        for interface in all_sensors:
            device_family = interface.mac_address[:2]
            device_id = f"{device_family}-{interface.mac_address[2:]}"
            if device_family not in DEVICE_SUPPORT_SYSBUS:
                _LOGGER.warning(
                    "Ignoring unknown device family (%s) found for device %s",
                    device_family,
                    device_id,
                )
                continue
            device_info: DeviceInfo = {
                ATTR_IDENTIFIERS: {(DOMAIN, device_id)},
                ATTR_MANUFACTURER: DEVICE_MANUFACTURER.get(
                    device_family, MANUFACTURER_MAXIM
                ),
                ATTR_MODEL: device_family,
                ATTR_NAME: device_id,
            }
            device = OWDirectDeviceDescription(
                device_info=device_info,
                interface=interface,
            )
            devices.append(device)
        return devices

    def _discover_devices_owserver(
        self, path: str = "/", parent_id: str | None = None
    ) -> list[OWDeviceDescription]:
        """Discover all owserver devices."""
        devices: list[OWDeviceDescription] = []
        assert self.owproxy
        for device_path in self.owproxy.dir(path):
            device_id = os.path.split(os.path.split(device_path)[0])[1]
            device_family = self.owproxy.read(f"{device_path}family").decode()
            _LOGGER.debug("read `%sfamily`: %s", device_path, device_family)
            device_type = self._get_device_type_owserver(device_path)
            if not _is_known_owserver_device(device_family, device_type):
                _LOGGER.warning(
                    "Ignoring unknown device family/type (%s/%s) found for device %s",
                    device_family,
                    device_type,
                    device_id,
                )
                continue
            device_info: DeviceInfo = {
                ATTR_IDENTIFIERS: {(DOMAIN, device_id)},
                ATTR_MANUFACTURER: DEVICE_MANUFACTURER.get(
                    device_family, MANUFACTURER_MAXIM
                ),
                ATTR_MODEL: device_type,
                ATTR_NAME: device_id,
            }
            if parent_id:
                device_info[ATTR_VIA_DEVICE] = (DOMAIN, parent_id)
            device = OWServerDeviceDescription(
                device_info=device_info,
                id=device_id,
                family=device_family,
                path=device_path,
                type=device_type,
            )
            devices.append(device)
            if device_branches := DEVICE_COUPLERS.get(device_family):
                for branch in device_branches:
                    devices += self._discover_devices_owserver(
                        f"{device_path}{branch}", device_id
                    )

        return devices

    def _get_device_type_owserver(self, device_path: str) -> str:
        """Get device model."""
        if TYPE_CHECKING:
            assert self.owproxy
        device_type = self.owproxy.read(f"{device_path}type").decode()
        _LOGGER.debug("read `%stype`: %s", device_path, device_type)
        if device_type == "EDS":
            device_type = self.owproxy.read(f"{device_path}device_type").decode()
            _LOGGER.debug("read `%sdevice_type`: %s", device_path, device_type)
        if TYPE_CHECKING:
            assert isinstance(device_type, str)
        return device_type

    def has_device_in_cache(self, device: DeviceEntry) -> bool:
        """Check if device was present in the cache."""
        if TYPE_CHECKING:
            assert self.devices
        for internal_device in self.devices:
            for identifier in internal_device.device_info[ATTR_IDENTIFIERS]:
                if identifier in device.identifiers:
                    return True
        return False


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidPath(HomeAssistantError):
    """Error to indicate the path is invalid."""
