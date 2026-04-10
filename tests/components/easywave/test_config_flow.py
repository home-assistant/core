"""Tests for the config flow of the Easywave Core integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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

COMPORTS_PATH = (
    "homeassistant.components.easywave.config_flow.serial.tools.list_ports.comports"
)


def _make_port(
    device: str = "/dev/ttyACM0",
    vid: int = 0x155A,
    pid: int = 0x1014,
    serial_number: str = "12345",
    manufacturer: str = "ELDAT",
    product: str = "RX11 USB Transceiver",
) -> MagicMock:
    """Create a mock serial port object."""
    port = MagicMock()
    port.device = device
    port.vid = vid
    port.pid = pid
    port.serial_number = serial_number
    port.manufacturer = manufacturer
    port.product = product
    return port


async def test_user_flow_no_devices(hass: HomeAssistant) -> None:
    """Test user flow aborts when no serial ports are found."""
    with patch(COMPORTS_PATH, return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_select_port(hass: HomeAssistant) -> None:
    """Test user flow shows port selection form and proceeds to confirm."""
    port = _make_port()

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test user flow creates entry after port selection and confirmation."""
    port = _make_port()

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Easywave Gateway"
    assert result["data"][CONF_DEVICE_PATH] == "/dev/ttyACM0"
    assert result["data"][CONF_USB_VID] == 0x155A
    assert result["data"][CONF_USB_PID] == 0x1014
    assert result["data"][CONF_USB_SERIAL_NUMBER] == "12345"


async def test_user_flow_multiple_ports(hass: HomeAssistant) -> None:
    """Test user flow with multiple serial ports shows selection form."""
    port1 = _make_port()
    port2 = _make_port(device="/dev/ttyACM1", serial_number="54321")

    with patch(COMPORTS_PATH, return_value=[port1, port2]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


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


async def test_user_flow_device_disappeared(hass: HomeAssistant) -> None:
    """Test user step shows error when selected device is no longer available."""
    port1 = _make_port()
    port2 = _make_port(device="/dev/ttyACM1", serial_number="54321")

    with patch(COMPORTS_PATH, return_value=[port1, port2]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # On re-scan the selected port is gone
    port3 = _make_port(device="/dev/ttyACM2", serial_number="99999")
    with patch(COMPORTS_PATH, return_value=[port2, port3]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
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


async def test_confirm_unique_id_from_vid_pid(hass: HomeAssistant) -> None:
    """Test unique_id falls back to VID/PID when serial is unknown."""
    port = _make_port(serial_number="unknown")

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "easywave_155A_1014"


async def test_confirm_unique_id_from_device_path(hass: HomeAssistant) -> None:
    """Test unique_id falls back to device path when serial is unknown and no VID/PID."""
    port = _make_port(vid=None, pid=None, serial_number="unknown")

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    with patch(COMPORTS_PATH, return_value=[port]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PATH: "/dev/ttyACM0"},
        )

    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "easywave__dev_ttyACM0"
