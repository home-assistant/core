"""Pytest configuration and fixtures for Easywave Core tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.easywave.const import (
    CONF_BUTTON_COUNT,
    CONF_DEVICE_DATA,
    CONF_DEVICE_PATH,
    CONF_DEVICE_TITLE,
    CONF_ENTRY_TYPE,
    CONF_OPERATING_TYPE,
    CONF_TRANSMITTER_SERIAL,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
    ENTRY_TYPE_TRANSMITTER,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_DEVICES
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

MOCK_TRANSMITTER_SERIAL = "aa" * 16
MOCK_TRANSMITTER_DEVICE_ID = f"transmitter_{MOCK_TRANSMITTER_SERIAL}"
MOCK_NEO_SENSOR_SERIAL = "bb" * 16
MOCK_NEO_SENSOR_DEVICE_ID = f"neo_sensor_{MOCK_NEO_SENSOR_SERIAL}"


def _device_record(
    device_id: str,
    title: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Return a device record for config entry options."""
    return {
        CONF_DEVICE_ID: device_id,
        CONF_DEVICE_TITLE: title,
        CONF_DEVICE_DATA: data,
    }


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock gateway ConfigEntry."""
    return MockConfigEntry(
        version=2,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
    )


@pytest.fixture
def mock_config_entry_with_transmitter() -> MockConfigEntry:
    """Return a gateway ConfigEntry with a transmitter device."""
    return MockConfigEntry(
        version=2,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options={
            CONF_DEVICES: [
                _device_record(
                    MOCK_TRANSMITTER_DEVICE_ID,
                    "Test Transmitter",
                    {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
                        CONF_TRANSMITTER_SERIAL: MOCK_TRANSMITTER_SERIAL,
                        CONF_OPERATING_TYPE: "1",
                        CONF_BUTTON_COUNT: 4,
                    },
                )
            ]
        },
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
