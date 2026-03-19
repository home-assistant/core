"""Tests for the config flow of the Easywave Core integration."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.easywave.config_flow import _find_easywave_devices
from homeassistant.components.easywave.const import (
    CONF_DEVICE_PATH,
    CONF_USB_PID,
    CONF_USB_SERIAL_NUMBER,
    CONF_USB_VID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_flow_no_devices(hass: HomeAssistant) -> None:
    """Test user flow aborts when no devices are found."""
    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_single_device(
    hass: HomeAssistant, mock_usb_device: dict[str, Any]
) -> None:
    """Test user flow with exactly one device goes to confirm."""
    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[mock_usb_device],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_user_flow_single_device_confirm(
    hass: HomeAssistant, mock_usb_device: dict[str, Any]
) -> None:
    """Test user flow with one device completes after confirmation."""
    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[mock_usb_device],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Easywave Gateway"
    assert result["data"][CONF_DEVICE_PATH] == "/dev/ttyACM0"
    assert result["data"][CONF_USB_VID] == 0x155A
    assert result["data"][CONF_USB_PID] == 0x1014
    assert result["data"][CONF_USB_SERIAL_NUMBER] == "12345"


async def test_user_flow_multiple_devices(
    hass: HomeAssistant, mock_usb_device: dict[str, Any]
) -> None:
    """Test user flow with multiple devices shows selection form."""
    device2 = {**mock_usb_device, "device": "/dev/ttyACM1", "serial_number": "54321"}

    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[mock_usb_device, device2],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "detect"


async def test_user_flow_multiple_devices_select(
    hass: HomeAssistant, mock_usb_device: dict[str, Any]
) -> None:
    """Test selecting a device from multiple goes to confirm and creates entry."""
    device2 = {**mock_usb_device, "device": "/dev/ttyACM1", "serial_number": "54321"}

    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[mock_usb_device, device2],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "detect"

    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[mock_usb_device, device2],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_PATH] == "/dev/ttyACM0"


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts when integration is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_flow_multiple_devices_device_disappeared(
    hass: HomeAssistant, mock_usb_device: dict[str, Any]
) -> None:
    """Test detect step shows error when selected device is no longer available."""
    device2 = {**mock_usb_device, "device": "/dev/ttyACM1", "serial_number": "54321"}

    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[mock_usb_device, device2],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "detect"

    # On re-scan two devices remain but the selected one is gone
    device3 = {**mock_usb_device, "device": "/dev/ttyACM2", "serial_number": "99999"}
    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[device2, device3],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "detect"
    assert result["errors"] == {"base": "device_no_longer_available"}


async def test_usb_discovery_flow(
    hass: HomeAssistant, mock_usb_discovery_info: UsbServiceInfo
) -> None:
    """Test USB auto-discovery shows confirm form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=mock_usb_discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_usb_discovery_flow_creates_entry(
    hass: HomeAssistant, mock_usb_discovery_info: UsbServiceInfo
) -> None:
    """Test USB discovery creates entry after confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=mock_usb_discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Easywave Gateway"
    assert result["data"][CONF_USB_VID] == 0x155A
    assert result["data"][CONF_USB_PID] == 0x1014


async def test_usb_discovery_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_usb_discovery_info: UsbServiceInfo,
) -> None:
    """Test USB discovery aborts when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=mock_usb_discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


def test_find_easywave_devices_with_mock(mock_serial_port: MagicMock) -> None:
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


def test_find_easywave_devices_no_ports() -> None:
    """Test _find_easywave_devices with no serial ports."""
    with patch(
        "homeassistant.components.easywave.config_flow.serial.tools.list_ports.comports",
        return_value=[],
    ):
        devices = _find_easywave_devices()

    assert devices == []


def test_find_easywave_devices_exception() -> None:
    """Test _find_easywave_devices when exception occurs."""
    with patch(
        "homeassistant.components.easywave.config_flow.serial.tools.list_ports.comports",
        side_effect=OSError("Port enumeration failed"),
    ):
        devices = _find_easywave_devices()

    assert devices == []


async def test_confirm_unique_id_from_vid_pid(
    hass: HomeAssistant,
) -> None:
    """Test unique_id falls back to VID/PID when serial is unknown."""
    device = {
        "device": "/dev/ttyACM0",
        "vid": 0x155A,
        "pid": 0x1014,
        "serial_number": "unknown",
        "manufacturer": "ELDAT",
        "product": "RX11 USB Transceiver",
    }

    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[device],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "easywave_155A_1014"


async def test_confirm_unique_id_from_device_path(
    hass: HomeAssistant,
) -> None:
    """Test unique_id falls back to device path when serial is unknown and no VID/PID."""
    device = {
        "device": "/dev/ttyACM0",
        "vid": None,
        "pid": None,
        "serial_number": "unknown",
        "manufacturer": "ELDAT",
        "product": "RX11 USB Transceiver",
    }

    with patch(
        "homeassistant.components.easywave.config_flow._find_easywave_devices",
        return_value=[device],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "easywave__dev_ttyACM0"
