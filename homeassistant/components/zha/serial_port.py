"""Utilities to list and identify serial ports."""

from __future__ import annotations

import dataclasses
import ipaddress
import pathlib
from typing import Self, cast
import urllib.parse

import serial.tools.list_ports

from homeassistant.components import zeroconf
from homeassistant.components.hassio import AddonError, AddonState
from homeassistant.components.homeassistant_hardware import silabs_multiprotocol_addon
from homeassistant.components.homeassistant_yellow import hardware as yellow_hardware
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


class SerialPortMissing(Exception):
    """Serial port is currently missing."""


class SerialPortNotUnique(Exception):
    """Serial port is not unique."""


@dataclasses.dataclass
class SystemSerialPort:
    """System serial port that is not associated with any USB device."""

    device: pathlib.Path
    product: str | None = None
    manufacturer: str | None = None

    @property
    def path(self) -> str:
        """Path to the serial port, usable by PySerial."""
        return str(self.device)

    @property
    def unique_id(self) -> str:
        """Unique ID of the serial port."""
        # We use `device` here because it is assumed to be 100% stable
        return f"SystemSerialPort:{self.device}"

    def display_name(self, *, hide_device: bool = True) -> str:
        """Human-readable display name of the serial port."""
        name = ""

        if self.product:
            name += self.product

        if self.manufacturer:
            if name:
                name += f" - {self.manufacturer}"
            else:
                name += self.manufacturer

        if (name and not hide_device) or not name:
            if name:
                name += f" ({self.device})"
            else:
                name += str(self.device)

        return name


@dataclasses.dataclass
class UsbSerialPort:
    """Serial port associated with a USB device."""

    device: pathlib.Path
    resolved_device: pathlib.Path

    vid: str
    pid: str
    serial_number: str | None = None

    product: str | None = None
    manufacturer: str | None = None

    @property
    def path(self) -> str:
        """Path to the serial port, usable by PySerial."""
        return str(self.device)

    @property
    def unique_id(self) -> str | None:
        """Unique ID of the serial port."""

        # Without a serial number, the port cannot be considered unique
        if self.serial_number is None:
            return None

        return (
            f"UsbSerialPort:{self.vid}:{self.pid}_{self.serial_number}"
            f"_{self.manufacturer}_{self.product}"
        )

    def display_name(self, *, hide_device: bool = True) -> str:
        """Human-readable display name of the serial port."""
        name = ""

        if self.product:
            name += self.product

        if self.manufacturer:
            if name:
                name += f" - {self.manufacturer}"
            else:
                name += self.manufacturer

        if self.serial_number:
            if name:
                name += f", s/n: {self.serial_number}"
            else:
                name += f"s/n: {self.serial_number}"

        if (name and not hide_device) or not name:
            if name:
                name += f" ({self.resolved_device})"
            else:
                name += str(self.resolved_device)

        return name


@dataclasses.dataclass
class NetworkSerialPort:
    """Serial port provided by a device on the network."""

    host: ipaddress.IPv4Address | ipaddress.IPv6Address | str
    port: int

    product: str | None = None
    manufacturer: str | None = None

    @classmethod
    def from_zeroconf(
        cls, service_info: zeroconf.ZeroconfServiceInfo, *, default_port: int
    ) -> Self:
        """Create a network serial port from a Zeroconf service."""
        return cls(
            host=service_info.ip_address,
            port=service_info.port or default_port,
            product=service_info.name,
            manufacturer=service_info.properties.get("manufacturer", None),
        )

    @property
    def path(self) -> str:
        """Path to the serial port, usable by PySerial."""
        return f"socket://{self.host}:{self.port}"

    @property
    def unique_id(self) -> str | None:
        """Unique ID of the serial port, if available."""
        return f"NetworkSerialPort:{self.host}:{self.port}"

    def display_name(self, *, hide_device: bool = True) -> str:
        """Human-readable display name of the serial port."""

        name = ""

        if self.product:
            name += self.product

        if self.manufacturer:
            if name:
                name += f" - {self.manufacturer}"
            else:
                name += self.manufacturer

        if (name and not hide_device) or not name:
            if name:
                name += f" ({self.host}:{self.port})"
            else:
                name += f"{self.host}:{self.port}"

        return name


def get_serial_symlinks() -> dict[pathlib.Path, pathlib.Path]:
    """Return a mapping of /dev/tty... to /dev/serial/by-id/... symlinks."""

    try:
        return {
            path.resolve(): path
            for path in pathlib.Path("/dev/serial/by-id/").iterdir()
            if path.is_symlink()
        }
    except FileNotFoundError:
        # Some installations may not have a `/dev/serial/by-id` directory
        return {}


async def async_list_serial_ports(
    hass: HomeAssistant,
) -> list[SystemSerialPort | UsbSerialPort]:
    """List all serial ports, including the Yellow radio."""
    try:
        yellow_hardware.async_info(hass)
    except HomeAssistantError:
        is_yellow = False
    else:
        is_yellow = True

    symlinks = await hass.async_add_executor_job(get_serial_symlinks)
    comports = await hass.async_add_executor_job(serial.tools.list_ports.comports)

    ports: list[UsbSerialPort | SystemSerialPort] = []

    for port in comports:
        if is_yellow and port.device == "/dev/ttyAMA1":
            ports.append(
                SystemSerialPort(
                    device=pathlib.Path(port.device),
                    manufacturer="Nabu Casa",
                    product="Yellow Zigbee Module",
                )
            )
        elif port.vid is not None:
            resolved_path = pathlib.Path(port.device)
            unique_path = symlinks[resolved_path]

            ports.append(
                UsbSerialPort(
                    device=unique_path,
                    resolved_device=resolved_path,
                    vid=port.vid,
                    pid=port.pid,
                    serial_number=port.serial_number,
                    manufacturer=port.manufacturer,
                    product=port.product,
                )
            )
        else:
            ports.append(SystemSerialPort(device=port.device))

    return ports


async def async_list_zha_serial_ports(
    hass: HomeAssistant,
) -> list[SystemSerialPort | UsbSerialPort | NetworkSerialPort]:
    """List all serial ports, including the Yellow radio and the multi-PAN addon."""

    ports = cast(
        list[SystemSerialPort | UsbSerialPort | NetworkSerialPort],
        await async_list_serial_ports(hass),
    )

    # Present the multi-PAN addon as a setup option, if it's available
    multipan_manager = await silabs_multiprotocol_addon.get_multiprotocol_addon_manager(
        hass
    )

    try:
        addon_info = await multipan_manager.async_get_addon_info()
    except (AddonError, KeyError):
        addon_info = None

    if addon_info is not None and addon_info.state != AddonState.NOT_INSTALLED:
        parsed = urllib.parse.urlparse(silabs_multiprotocol_addon.get_zigbee_socket())
        assert parsed.hostname is not None
        assert parsed.port is not None

        ports.append(
            NetworkSerialPort(
                host=parsed.hostname,
                port=parsed.port,
                product="Multiprotocol add-on",
                manufacturer="Nabu Casa",
            )
        )

    return ports


async def async_find_unique_port(
    hass: HomeAssistant, path: str
) -> SystemSerialPort | UsbSerialPort:
    """Find a unique system or USB serial port based on a path."""
    ports = await async_list_serial_ports(hass)
    resolved_path = await hass.async_add_executor_job(pathlib.Path(path).resolve)

    candidates = [
        port
        for port in ports
        if port.path == path
        or (isinstance(port, UsbSerialPort) and port.resolved_device == resolved_path)
    ]

    if len(candidates) > 1:
        raise SerialPortNotUnique(f"Serial port {path} is not unique: {candidates}")

    if not candidates:
        raise SerialPortMissing(f"Serial port {path} does not exist")

    return candidates[0]


async def async_serial_port_from_path(
    hass: HomeAssistant, path: str
) -> SystemSerialPort | UsbSerialPort | NetworkSerialPort:
    """Identify which serial port a specific path points to."""
    if not path.startswith("socket://"):
        return await async_find_unique_port(hass, path)

    # Network serial ports are always unique
    host, network_port = path.removeprefix("socket://").rsplit(":", 1)

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return NetworkSerialPort(host=host, port=int(network_port))

    return NetworkSerialPort(host=ip, port=int(network_port))
