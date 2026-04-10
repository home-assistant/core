"""Pytest configuration and fixtures for Easywave Core tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.easywave.const import (
    CONF_DEVICE_PATH,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
)
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from tests.common import MockConfigEntry

MOCK_ENTRY_DATA = {
    CONF_DEVICE_PATH: "/dev/ttyACM0",
    CONF_USB_VID: 0x155A,
    CONF_USB_PID: 0x1014,
    CONF_USB_SERIAL_NUMBER: "12345",
    CONF_USB_MANUFACTURER: "ELDAT",
    CONF_USB_PRODUCT: "RX11 USB Transceiver",
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock ConfigEntry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
    )


@pytest.fixture
def mock_usb_discovery_info() -> UsbServiceInfo:
    """Return a mock USB discovery info."""
    return UsbServiceInfo(
        device="/dev/ttyACM0",
        vid="155A",
        pid="1014",
        serial_number="12345",
        manufacturer="ELDAT",
        description="RX11 USB Transceiver",
    )


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Return a mock EasywaveCoordinator."""
    coordinator = MagicMock()
    coordinator.async_setup = AsyncMock(return_value=True)
    coordinator.async_shutdown = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    coordinator.is_offline = False
    coordinator.transceiver = MagicMock()
    coordinator.transceiver.is_connected = True
    coordinator.transceiver.usb_serial_number = "12345"
    coordinator.transceiver.hw_version = "1.0"
    coordinator.transceiver.fw_version = "2.0"
    coordinator.transceiver.device_path = "/dev/ttyACM0"
    return coordinator


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.easywave.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
