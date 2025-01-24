"""Hub for communication with 1-Wire server or mount_dir."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import os

from pyownet import protocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_VIA_DEVICE, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.signal_type import SignalType

from .const import (
    DEVICE_SUPPORT,
    DOMAIN,
    MANUFACTURER_EDS,
    MANUFACTURER_HOBBYBOARDS,
    MANUFACTURER_MAXIM,
)
from .model import OWDeviceDescription

DEVICE_COUPLERS = {
    # Family : [branches]
    "1F": ["aux", "main"]
}

DEVICE_MANUFACTURER = {
    "7E": MANUFACTURER_EDS,
    "EF": MANUFACTURER_HOBBYBOARDS,
}

_DEVICE_SCAN_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)

type OneWireConfigEntry = ConfigEntry[OneWireHub]

SIGNAL_NEW_DEVICE_CONNECTED = SignalType["OneWireHub", list[OWDeviceDescription]](
    f"{DOMAIN}_new_device_connected"
)


def _is_known_device(device_family: str, device_type: str | None) -> bool:
    """Check if device family/type is known to the library."""
    if device_family in ("7E", "EF"):  # EDS or HobbyBoard
        return device_type in DEVICE_SUPPORT[device_family]
    return device_family in DEVICE_SUPPORT


class OneWireHub:
    """Hub to communicate with server."""

    owproxy: protocol._Proxy
    devices: list[OWDeviceDescription]

    def __init__(self, hass: HomeAssistant, config_entry: OneWireConfigEntry) -> None:
        """Initialize."""
        self._hass = hass
        self._config_entry = config_entry

    def _initialize(self) -> None:
        """Connect to the server, and discover connected devices.

        Needs to be run in executor.
        """
        host = self._config_entry.data[CONF_HOST]
        port = self._config_entry.data[CONF_PORT]
        _LOGGER.debug("Initializing connection to %s:%s", host, port)
        self.owproxy = protocol.proxy(host, port)
        self.devices = _discover_devices(self.owproxy)

    async def initialize(self) -> None:
        """Initialize a config entry."""
        await self._hass.async_add_executor_job(self._initialize)
        self._populate_device_registry(self.devices)

    @callback
    def _populate_device_registry(self, devices: list[OWDeviceDescription]) -> None:
        """Populate the device registry."""
        device_registry = dr.async_get(self._hass)
        for device in devices:
            device_registry.async_get_or_create(
                config_entry_id=self._config_entry.entry_id,
                **device.device_info,
            )

    def schedule_scan_for_new_devices(self) -> None:
        """Schedule a regular scan of the bus for new devices."""
        self._config_entry.async_on_unload(
            async_track_time_interval(
                self._hass, self._scan_for_new_devices, _DEVICE_SCAN_INTERVAL
            )
        )

    async def _scan_for_new_devices(self, _: datetime) -> None:
        """Scan the bus for new devices."""
        devices = await self._hass.async_add_executor_job(
            _discover_devices, self.owproxy
        )
        existing_device_ids = [device.id for device in self.devices]
        new_devices = [
            device for device in devices if device.id not in existing_device_ids
        ]
        if new_devices:
            self.devices.extend(new_devices)
            self._populate_device_registry(new_devices)
            async_dispatcher_send(
                self._hass, SIGNAL_NEW_DEVICE_CONNECTED, self, new_devices
            )


def _discover_devices(
    owproxy: protocol._Proxy, path: str = "/", parent_id: str | None = None
) -> list[OWDeviceDescription]:
    """Discover all server devices."""
    devices: list[OWDeviceDescription] = []
    for device_path in owproxy.dir(path):
        device_id = os.path.split(os.path.split(device_path)[0])[1]
        device_family = owproxy.read(f"{device_path}family").decode()
        _LOGGER.debug("read `%sfamily`: %s", device_path, device_family)
        device_type = _get_device_type(owproxy, device_path)
        if not _is_known_device(device_family, device_type):
            _LOGGER.warning(
                "Ignoring unknown device family/type (%s/%s) found for device %s",
                device_family,
                device_type,
                device_id,
            )
            continue
        device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=DEVICE_MANUFACTURER.get(device_family, MANUFACTURER_MAXIM),
            model=device_type,
            model_id=device_type,
            name=device_id,
            serial_number=device_id[3:],
        )
        if parent_id:
            device_info[ATTR_VIA_DEVICE] = (DOMAIN, parent_id)
        device = OWDeviceDescription(
            device_info=device_info,
            id=device_id,
            family=device_family,
            path=device_path,
            type=device_type,
        )
        devices.append(device)
        if device_branches := DEVICE_COUPLERS.get(device_family):
            for branch in device_branches:
                devices += _discover_devices(
                    owproxy, f"{device_path}{branch}", device_id
                )

    return devices


def _get_device_type(owproxy: protocol._Proxy, device_path: str) -> str | None:
    """Get device model."""
    try:
        device_type: str = owproxy.read(f"{device_path}type").decode()
    except protocol.ProtocolError as exc:
        _LOGGER.debug("Unable to read `%stype`: %s", device_path, exc)
        return None
    _LOGGER.debug("read `%stype`: %s", device_path, device_type)
    if device_type == "EDS":
        device_type = owproxy.read(f"{device_path}device_type").decode()
        _LOGGER.debug("read `%sdevice_type`: %s", device_path, device_type)
    return device_type
