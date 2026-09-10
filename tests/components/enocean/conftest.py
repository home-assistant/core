"""Fixtures for EnOcean integration tests."""

from typing import Final

import pytest

from homeassistant.components.enocean.const import (
    CONFIG_FLOW_MINOR_VERSION,
    CONFIG_FLOW_VERSION,
    DOMAIN,
)
from homeassistant.components.usb import USBDevice
from homeassistant.const import CONF_DEVICE
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from . import MOCK_USB_DEVICE

from tests.common import MockConfigEntry

ENTRY_CONFIG: Final[dict[str, str]] = {
    CONF_DEVICE: "/dev/ttyUSB0",
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="device_chip_id",
        data=ENTRY_CONFIG,
        version=CONFIG_FLOW_VERSION,
        minor_version=CONFIG_FLOW_MINOR_VERSION,
    )


@pytest.fixture
def mock_usb_device() -> USBDevice:
    """Return a mocked usb device."""
    return USBDevice(
        device=MOCK_USB_DEVICE.device,
        pid=MOCK_USB_DEVICE.pid,
        vid=MOCK_USB_DEVICE.vid,
        serial_number=MOCK_USB_DEVICE.serial_number,
        manufacturer=MOCK_USB_DEVICE.manufacturer,
        description=MOCK_USB_DEVICE.description,
    )


@pytest.fixture
def mock_usb_service_info() -> UsbServiceInfo:
    """Return a mocked usb service info."""
    return UsbServiceInfo(
        device=MOCK_USB_DEVICE.device,
        vid=MOCK_USB_DEVICE.vid,
        pid=MOCK_USB_DEVICE.pid,
        serial_number=MOCK_USB_DEVICE.serial_number,
        manufacturer=MOCK_USB_DEVICE.manufacturer,
        description=MOCK_USB_DEVICE.description,
    )
