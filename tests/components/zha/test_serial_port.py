"""Test serial port utilities."""

import ipaddress
import pathlib

from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.components.zha.serial_port import (
    NetworkSerialPort,
    SystemSerialPort,
    UsbSerialPort,
)


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
