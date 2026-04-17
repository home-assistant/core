"""Test the Teleinfo config flow."""

from unittest.mock import MagicMock

import pytest
import serial

from homeassistant.components.teleinfo.const import CONF_SERIAL_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .conftest import USB_DISCOVERY_INFO

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_teleinfo")
async def test_user_flow_success(
    hass: HomeAssistant, mock_serial_port: MagicMock
) -> None:
    """Test the full happy path: serial port opens, frame is read and decoded."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Teleinfo (/dev/ttyUSB0)"

    config_entry = result["result"]
    assert config_entry.unique_id == "021861348497"
    assert config_entry.data == {
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (serial.SerialException("Port not found"), "cannot_connect"),
        (TimeoutError("No data"), "timeout_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_teleinfo")
async def test_user_flow_error_recovery(
    hass: HomeAssistant,
    mock_serial_port: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test the flow recovers after each failure mode when the port starts working."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_serial_port.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB0"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Recover: the port now works.
    mock_serial_port.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB0"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Teleinfo (/dev/ttyUSB0)"


@pytest.mark.usefixtures("mock_teleinfo")
async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_serial_port: MagicMock,
) -> None:
    """Test we abort when the same serial port is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB0"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_decode_error(
    hass: HomeAssistant, mock_teleinfo: MagicMock, mock_serial_port: MagicMock
) -> None:
    """Test we handle decode errors from pyteleinfo."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_teleinfo.decode.side_effect = mock_teleinfo.TeleinfoError("bad frame")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB0"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}

    mock_teleinfo.decode.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB0"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_teleinfo")
async def test_usb_discovery_success(
    hass: HomeAssistant, mock_serial_port: MagicMock
) -> None:
    """Test USB discovery happy path: detect → validate → confirm → create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Teleinfo (/dev/ttyUSB0)"
    assert result["data"] == {CONF_SERIAL_PORT: "/dev/ttyUSB0"}
    assert result["result"].unique_id == "021861348497"


@pytest.mark.usefixtures("mock_teleinfo")
async def test_usb_discovery_not_teleinfo(
    hass: HomeAssistant, mock_serial_port: MagicMock
) -> None:
    """Test USB discovery aborts when frame read times out (not a Teleinfo device)."""
    mock_serial_port.side_effect = TimeoutError("No data received")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_teleinfo_device"


@pytest.mark.usefixtures("mock_teleinfo")
async def test_usb_discovery_already_configured_updates_path(
    hass: HomeAssistant, mock_serial_port: MagicMock
) -> None:
    """Test USB discovery updates device path when dongle is re-plugged."""

    # Existing entry with same ADCO but old path
    existing_entry = MockConfigEntry(
        title="Teleinfo (/dev/ttyUSB-old)",
        domain=DOMAIN,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB-old"},
        unique_id="021861348497",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=UsbServiceInfo(
            device="/dev/ttyUSB-new",
            pid="6015",
            vid="0403",
            serial_number="AB1234",
            manufacturer="FTDI",
            description="FT230X Basic UART",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Path should be updated to the new device path
    assert existing_entry.data[CONF_SERIAL_PORT] == "/dev/ttyUSB-new"


@pytest.mark.usefixtures("mock_teleinfo")
async def test_usb_discovery_manual_entry_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_serial_port: MagicMock,
) -> None:
    """Test USB discovery aborts when the meter was already added manually."""

    # mock_config_entry has ADCO unique_id — same as what USB discovery will find
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_usb_discovery_decode_error_aborts(
    hass: HomeAssistant,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test USB discovery aborts when frame is read but decode fails."""

    mock_teleinfo.decode.side_effect = mock_teleinfo.TeleinfoError("bad frame")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USB},
        data=USB_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_teleinfo_device"
