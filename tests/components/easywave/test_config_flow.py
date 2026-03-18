"""Tests for the config flow of the Easywave Core integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from typing import Any

import pytest
from homeassistant.components import usb
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from homeassistant.components.easywave.config_flow import (
    EasywaveConfigFlow,
    _find_easywave_devices,
)
from homeassistant.components.easywave.const import (
    CONF_DEVICE_PATH,
    CONF_USB_MANUFACTURER,
    CONF_USB_PID,
    CONF_USB_PRODUCT,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_async_step_user_no_devices(hass: HomeAssistant):
    """Test async_step_user when no devices are found."""
    flow = EasywaveConfigFlow()
    
    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[],
    ):
        result = await flow.async_step_user()
    
    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_found"


@pytest.mark.asyncio
async def test_async_step_user_single_device(hass: HomeAssistant, mock_usb_device: dict[str, Any]):
    """Test async_step_user with exactly one device found."""
    flow = EasywaveConfigFlow()
    
    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[mock_usb_device],
    ):
        result = await flow.async_step_user()
    
    # Should skip to confirm step
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"


@pytest.mark.asyncio
async def test_async_step_user_multiple_devices(
    hass: HomeAssistant, mock_usb_device: dict[str, Any]
):
    """Test async_step_user with multiple devices found."""
    flow = EasywaveConfigFlow()
    device2 = {**mock_usb_device, "device": "/dev/ttyACM1", "serial_number": "54321"}
    
    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[mock_usb_device, device2],
    ):
        result = await flow.async_step_user()
    
    # Should show device selection form
    assert result["type"] == "form"
    assert result["step_id"] == "detect"


@pytest.mark.asyncio
async def test_async_step_detect_selection(
    hass: HomeAssistant, mock_usb_device: dict[str, Any]
):
    """Test async_step_detect when user selects a device."""
    flow = EasywaveConfigFlow()
    device2 = {**mock_usb_device, "device": "/dev/ttyACM1", "serial_number": "54321"}
    
    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[mock_usb_device, device2],
    ):
        result = await flow.async_step_detect(
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"}
        )
    
    # Should go to confirm step
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert flow._device == mock_usb_device


@pytest.mark.asyncio
async def test_async_step_usb(hass: HomeAssistant, mock_usb_discovery_info: usb.UsbServiceInfo):
    """Test async_step_usb for USB auto-discovery."""
    flow = EasywaveConfigFlow()
    flow.hass = hass
    
    result = await flow.async_step_usb(mock_usb_discovery_info)
    
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert flow._device["device"] == "/dev/ttyACM0"
    assert flow._device["vid"] == 0x155A
    assert flow._device["pid"] == 0x1014


@pytest.mark.asyncio
async def test_async_step_usb_already_configured(
    hass: HomeAssistant, 
    mock_config_entry: ConfigEntry,
    mock_usb_discovery_info: usb.UsbServiceInfo,
):
    """Test async_step_usb when device is already configured."""
    mock_config_entry.read_only = True
    hass.config_entries._entries.append(mock_config_entry)
    
    flow = EasywaveConfigFlow()
    flow.hass = hass
    
    result = await flow.async_step_usb(mock_usb_discovery_info)
    
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_async_step_confirm(hass: HomeAssistant, mock_usb_device: dict[str, Any]):
    """Test async_step_confirm form display."""
    flow = EasywaveConfigFlow()
    flow.hass = hass
    flow._device = mock_usb_device
    
    result = await flow.async_step_confirm()
    
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert "RX11 USB Transceiver" in str(result["description_placeholders"])


@pytest.mark.asyncio
async def test_async_step_confirm_submit(hass: HomeAssistant, mock_usb_device: dict[str, Any]):
    """Test async_step_confirm with user submission."""
    flow = EasywaveConfigFlow()
    flow.hass = hass
    flow._device = mock_usb_device
    
    result = await flow.async_step_confirm(user_input={})
    
    assert result["type"] == "create_entry"
    assert result["title"] == "Easywave Gateway"
    assert result["data"][CONF_DEVICE_PATH] == "/dev/ttyACM0"
    assert result["data"][CONF_USB_VID] == 0x155A
    assert result["data"][CONF_USB_PID] == 0x1014
    assert result["data"][CONF_USB_SERIAL_NUMBER] == "12345"


def test_find_easywave_devices_with_mock(mock_serial_port):
    """Test _find_easywave_devices with mocked serial ports."""
    with patch(
        "homeassistant.components.easywave.config_flow.serial.tools.list_ports.comports",
        return_value=[mock_serial_port],
    ):
        devices = _find_easywave_devices()
    
    assert len(devices) == 1
    assert devices[0]["device"] == "/dev/ttyACM0"
    assert devices[0]["vid"] == 0x155A
    assert devices[0]["pid"] == 0x1014


def test_find_easywave_devices_no_ports():
    """Test _find_easywave_devices with no serial ports."""
    with patch(
        "homeassistant.components.easywave.config_flow.serial.tools.list_ports.comports",
        return_value=[],
    ):
        devices = _find_easywave_devices()
    
    assert devices == []


def test_find_easywave_devices_exception():
    """Test _find_easywave_devices when exception occurs."""
    with patch(
        "homeassistant.components.easywave.config_flow.serial.tools.list_ports.comports",
        side_effect=Exception("Port enumeration failed"),
    ):
        devices = _find_easywave_devices()
    
    assert devices == []
