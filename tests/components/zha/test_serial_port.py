"""Test serial port utilities."""

import ipaddress
import pathlib
from typing import Any
from unittest.mock import patch

from serial.tools.list_ports_common import ListPortInfo

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.components.zha.serial_port import (
    NetworkSerialPort,
    SystemSerialPort,
    UsbSerialPort,
    async_list_serial_ports,
)
from homeassistant.core import HomeAssistant


def test_system_serial_port() -> None:
    """Test `SystemSerialPort`."""

    port = SystemSerialPort(
        device=pathlib.PurePosixPath("/dev/ttyAMA1"),
        product="product",
        manufacturer="manufacturer",
    )

    assert port.path == "/dev/ttyAMA1"
    assert port.unique_id == "SystemSerialPort:/dev/ttyAMA1_manufacturer_product"
    assert port.display_name() == "product - manufacturer"

    port.product = None
    assert port.display_name() == "manufacturer"
    assert port.display_name(hide_device=False) == "manufacturer (/dev/ttyAMA1)"
    assert port.unique_id == "SystemSerialPort:/dev/ttyAMA1_manufacturer_None"

    port.manufacturer = None
    assert port.display_name() == "/dev/ttyAMA1"
    assert port.display_name(hide_device=False) == "/dev/ttyAMA1"
    assert port.unique_id == "SystemSerialPort:/dev/ttyAMA1_None_None"


def test_usb_serial_port() -> None:
    """Test `UsbSerialPort`."""

    port = UsbSerialPort(
        device=pathlib.PurePosixPath("/dev/serial/by-id/unique"),
        resolved_device=pathlib.PurePosixPath("/dev/ttyUSB0"),
        vid="1234",
        pid="ABCD",
        serial_number="serialnumber",
        product="product",
        manufacturer="manufacturer",
    )

    assert port.path == "/dev/serial/by-id/unique"
    assert port.unique_id == "UsbSerialPort:1234:ABCD_serialnumber_manufacturer_product"
    assert port.display_name() == "product - manufacturer, s/n: serialnumber"
    assert (
        port.display_name(hide_device=False)
        == "product - manufacturer, s/n: serialnumber (/dev/ttyUSB0)"
    )

    port.product = None
    assert port.display_name() == "manufacturer, s/n: serialnumber"
    assert port.unique_id == "UsbSerialPort:1234:ABCD_serialnumber_manufacturer_None"

    port.manufacturer = None
    assert port.display_name() == "s/n: serialnumber"
    assert port.unique_id == "UsbSerialPort:1234:ABCD_serialnumber_None_None"

    port.serial_number = None
    assert port.display_name() == "/dev/ttyUSB0"
    assert port.display_name(hide_device=False) == "/dev/ttyUSB0"
    assert port.unique_id is None


def test_network_serial_port() -> None:
    """Test `NetworkSerialPort`."""

    port = NetworkSerialPort(
        host=ipaddress.ip_address("1.2.3.4"),
        port=5678,
        product="product",
        manufacturer="manufacturer",
    )

    assert port.path == "socket://1.2.3.4:5678"
    assert port.unique_id == "NetworkSerialPort:1.2.3.4:5678"
    assert port.display_name() == "product - manufacturer"
    assert (
        port.display_name(hide_device=False) == "product - manufacturer (1.2.3.4:5678)"
    )

    port.product = None
    assert port.display_name() == "manufacturer"

    port.manufacturer = None
    assert port.display_name() == "1.2.3.4:5678"


def test_network_serial_port_from_zeroconf() -> None:
    """Test `NetworkSerialPort` construction from ZeroConf service info."""

    service_info = ZeroconfServiceInfo(
        ip_address=ipaddress.ip_address("192.168.1.200"),
        ip_addresses=[ipaddress.ip_address("192.168.1.200")],
        hostname="tube._tube_zb_gw._tcp.local.",
        name="tube",
        port=6053,
        properties={"name": "tube_123456", "manufacturer": "tubeszb"},
        type="mock_type",
    )

    port = NetworkSerialPort.from_zeroconf(service_info, default_port=1234)

    assert port == NetworkSerialPort(
        host=ipaddress.ip_address("192.168.1.200"),
        port=6053,
        product="tube",
        manufacturer="tubeszb",
    )


def make_pyserial_port(device: str, **kwargs: Any) -> ListPortInfo:
    """Create a PySerial port."""
    port = ListPortInfo(device, skip_link_detection=True)

    for key, value in kwargs.items():
        assert hasattr(port, key)
        setattr(port, key, value)

    return port


async def test_list_serial_ports(hass: HomeAssistant) -> None:
    """Test listing all serial ports."""

    with (
        patch(
            "homeassistant.components.zha.serial_port.yellow_hardware.async_info",
            side_effect=None,
        ),
        patch(
            "homeassistant.components.zha.serial_port.get_serial_symlinks",
            return_value={
                pathlib.Path("/dev/ttyUSB0"): pathlib.Path(
                    "/dev/serial/by-id/usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1_d8d6a1d223edec1199274540ad51a8b2-if00-port0"
                )
            },
        ),
        patch(
            "homeassistant.components.zha.serial_port.serial.tools.list_ports.comports",
            return_value=[
                make_pyserial_port(
                    device="/dev/ttyUSB0",
                    vid=0x10C4,
                    pid=0xEA60,
                    serial_number="d8d6a1d223edec1199274540ad51a8b2",
                    manufacturer="Nabu Casa",
                    product="SkyConnect v1.0",
                ),
                make_pyserial_port(device="/dev/ttyAMA1"),
            ],
        ),
    ):
        ports = await async_list_serial_ports(hass)

    assert ports == [
        UsbSerialPort(
            device=pathlib.Path(
                "/dev/serial/by-id/usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1_d8d6a1d223edec1199274540ad51a8b2-if00-port0"
            ),
            resolved_device=pathlib.Path("/dev/ttyUSB0"),
            vid=0x10C4,
            pid=0xEA60,
            serial_number="d8d6a1d223edec1199274540ad51a8b2",
            manufacturer="Nabu Casa",
            product="SkyConnect v1.0",
        ),
        SystemSerialPort(
            device=pathlib.Path("/dev/ttyAMA1"),
            manufacturer="Nabu Casa",
            product="Yellow Zigbee Module",
        ),
    ]
