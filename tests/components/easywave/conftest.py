"""Pytest configuration and fixtures for Easywave Core tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

import pytest
from homeassistant.components import usb
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from homeassistant.components.easywave.const import (
    CONF_DEVICE_PATH,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
)


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Return a mock ConfigEntry."""
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data={
            CONF_DEVICE_PATH: "/dev/ttyACM0",
            CONF_USB_VID: 0x155A,
            CONF_USB_PID: 0x1014,
            CONF_USB_SERIAL_NUMBER: "12345",
            CONF_USB_MANUFACTURER: "ELDAT",
            CONF_USB_PRODUCT: "RX11 USB Transceiver",
        },
        source="usb",
        unique_id="easywave_12345",
    )


@pytest.fixture
def mock_usb_device() -> dict[str, Any]:
    """Return a mock USB device info dict."""
    return {
        "device": "/dev/ttyACM0",
        "vid": 0x155A,
        "pid": 0x1014,
        "serial_number": "12345",
        "manufacturer": "ELDAT",
        "product": "RX11 USB Transceiver",
    }


@pytest.fixture
def mock_usb_discovery_info() -> usb.UsbServiceInfo:
    """Return a mock USB discovery info."""
    return usb.UsbServiceInfo(
        device="/dev/ttyACM0",
        vid="155A",
        pid="1014",
        serial_number="12345",
        manufacturer="ELDAT",
        description="RX11 USB Transceiver",
    )


@pytest.fixture
def mock_serial_port():
    """Return a mock serial port."""
    port = MagicMock()
    port.device = "/dev/ttyACM0"
    port.vid = 0x155A
    port.pid = 0x1014
    port.serial_number = "12345"
    port.manufacturer = "ELDAT"
    return port


@pytest.fixture
def mock_device_registry(hass: HomeAssistant) -> dr.DeviceRegistry:
    """Return the device registry."""
    return dr.async_get(hass)


@pytest.fixture
async def mock_hass(hass: HomeAssistant) -> HomeAssistant:
    """Return a mock Home Assistant instance with test data."""
    hass.data[DOMAIN] = {}
    return hass
