"""Utilities to list and identify serial ports."""

from __future__ import annotations

import dataclasses
import ipaddress
import pathlib

import serial.tools.list_ports

from homeassistant.components import usb
from homeassistant.components.hassio import AddonError, AddonState
from homeassistant.components.homeassistant_hardware import silabs_multiprotocol_addon
from homeassistant.components.homeassistant_yellow import hardware as yellow_hardware
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


class SerialPortMissing(Exception):
    """Serial port is currently missing."""


@dataclasses.dataclass
class SystemSerialPort:
    """System serial port that is not associated with any USB device."""

    device: pathlib.Path
    description: str | None = None
    manufacturer: str | None = None

    @property
    def path(self) -> str:
        """Path to the serial port, usable by PySerial."""
        return str(self.device)

    @property
    def unique_id(self) -> str:
        """Unique ID of the serial port."""
        # We use `device` here because it is assumed to be 100% stable
        return f"SystemSerialPort:{self.device}_{self.manufacturer}_{self.description}"

    @property
    def display_name(self) -> str:
        """Human-readable display name of the serial port."""
        return f"{self.device}" + (
            f" - {self.manufacturer}" if self.manufacturer else ""
        )


@dataclasses.dataclass
class UsbSerialPort:
    """Serial port associated with a USB device."""

    device: pathlib.Path
    resolved_device: pathlib.Path

    vid: str
    pid: str
    serial_number: str | None = None

    description: str | None = None
    manufacturer: str | None = None

    @property
    def path(self) -> str:
        """Path to the serial port, usable by PySerial."""
        return str(self.device)

    @property
    def unique_id(self) -> str:
        """Unique ID of the serial port."""
        return (
            f"UsbSerialPort:{self.vid}:{self.pid}_{self.serial_number}"
            f"_{self.manufacturer}_{self.description}"
        )

    @property
    def display_name(self) -> str:
        """Human-readable display name of the serial port."""
        return (
            f"{self.resolved_device}"
            + (f", s/n: {self.serial_number}" if self.serial_number else "")
            + (f" - {self.manufacturer}" if self.manufacturer else "")
        )


@dataclasses.dataclass
class NetworkSerialPort:
    """Serial port provided by a device on the network."""

    host: ipaddress.IPv4Address | ipaddress.IPv6Address | str
    port: int

    description: str | None = None
    manufacturer: str | None = None

    @property
    def path(self) -> str:
        """Path to the serial port, usable by PySerial."""
        return f"socket://{self.host}:{self.port}"

    @property
    def unique_id(self) -> str | None:
        """Unique ID of the serial port, if available."""
        # Network serial ports pointing to raw IP addresses have no unique ID
        if isinstance(self.host, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            return None

        return f"NetworkSerialPort:{self.host}:{self.port}"

    @property
    def display_name(self) -> str:
        """Human-readable display name of the serial port."""
        return f"{self.path}" + (f" - {self.manufacturer}" if self.manufacturer else "")


async def async_list_serial_ports(
    hass: HomeAssistant,
) -> list[SystemSerialPort | UsbSerialPort | NetworkSerialPort]:
    """List all serial ports, including the Yellow radio and the multi-PAN addon."""
    try:
        yellow_hardware.async_info(hass)
    except HomeAssistantError:
        is_yellow = False
    else:
        is_yellow = True

    ports: list[SystemSerialPort | UsbSerialPort | NetworkSerialPort] = []
    comports = await hass.async_add_executor_job(serial.tools.list_ports.comports)

    for port in comports:
        if is_yellow and port.device == "/dev/ttyAMA1":
            ports.append(
                SystemSerialPort(
                    device=port.device,
                    manufacturer="Nabu Casa",
                    description="Yellow Zigbee Module",
                )
            )
        elif port.vid is not None:
            unique_path = await hass.async_add_executor_job(
                usb.get_serial_by_id, port.device
            )
            resolved_path = await hass.async_add_executor_job(
                pathlib.Path(port.device).resolve
            )

            ports.append(
                UsbSerialPort(
                    device=pathlib.Path(unique_path),
                    resolved_device=resolved_path,
                    vid=port.vid,
                    pid=port.pid,
                    serial_number=port.serial_number,
                    manufacturer=port.manufacturer,
                    description=port.description,
                )
            )
        else:
            ports.append(SystemSerialPort(device=port.device))

    # Present the multi-PAN addon as a setup option, if it's available
    multipan_manager = await silabs_multiprotocol_addon.get_multiprotocol_addon_manager(
        hass
    )

    try:
        addon_info = await multipan_manager.async_get_addon_info()
    except (AddonError, KeyError):
        addon_info = None

    if addon_info is not None and addon_info.state != AddonState.NOT_INSTALLED:
        host, port = (
            silabs_multiprotocol_addon.get_zigbee_socket()
            .replace("socket://", "", 1)
            .rsplit(":", 1)
        )

        ports.append(
            NetworkSerialPort(
                host=host,
                port=int(port),
                description="Multiprotocol add-on",
                manufacturer="Nabu Casa",
            )
        )

    return ports


async def async_serial_port_from_path(
    hass: HomeAssistant, path: str
) -> SystemSerialPort | UsbSerialPort | NetworkSerialPort:
    """Identify which serial port a specific path points to."""
    # Try to parse a network serial port first
    if path.startswith("socket://"):
        host, network_port = path.replace("socket://", "", 1).rsplit(":", 1)

        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return NetworkSerialPort(host=host, port=int(network_port))

        return NetworkSerialPort(host=ip, port=int(network_port))

    candidates: list[SystemSerialPort | UsbSerialPort | NetworkSerialPort] = []
    ports = await async_list_serial_ports(hass)
    resolved_path = await hass.async_add_executor_job(pathlib.Path(path).resolve)

    for port in ports:
        if port.path == path or (
            isinstance(port, UsbSerialPort) and port.resolved_device == resolved_path
        ):
            candidates.append(port)

    if len(candidates) > 1:
        raise ValueError(f"Serial port {path} is not unique: {candidates}")

    if not candidates:
        raise SerialPortMissing(f"Serial port {path} does not exist")

    return candidates[0]
