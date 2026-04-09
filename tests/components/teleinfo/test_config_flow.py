"""Test the Teleinfo config flow."""

from unittest.mock import MagicMock, patch

import pytest
import serial

from homeassistant.components.teleinfo.const import CONF_SERIAL_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import USB_DISCOVERY_INFO

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

PATCH_READ_FRAME = "homeassistant.components.teleinfo.config_flow.read_frame"


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


@pytest.mark.usefixtures("mock_teleinfo")
async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle serial port that doesn't exist or has permission issues."""
    with patch(
        PATCH_READ_FRAME,
        side_effect=serial.SerialException("Port not found"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_SERIAL_PORT: "/dev/ttyUSB0",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_teleinfo")
async def test_user_flow_timeout(hass: HomeAssistant) -> None:
    """Test we handle a port that exists but has no Teleinfo dongle (timeout)."""
    with patch(
        PATCH_READ_FRAME,
        side_effect=TimeoutError("No data received"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_SERIAL_PORT: "/dev/ttyUSB0",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "timeout_connect"}


@pytest.mark.usefixtures("mock_teleinfo")
async def test_user_flow_cannot_connect_recovery(
    hass: HomeAssistant, mock_serial_port: MagicMock
) -> None:
    """Test recovery after a serial connection error."""
    with patch(
        PATCH_READ_FRAME,
        side_effect=serial.SerialException("Port not found"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_SERIAL_PORT: "/dev/ttyUSB0",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover: now the port works (mock_serial_port fixture takes over)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Teleinfo (/dev/ttyUSB0)"


@pytest.mark.usefixtures("mock_teleinfo")
async def test_user_flow_timeout_recovery(
    hass: HomeAssistant, mock_serial_port: MagicMock
) -> None:
    """Test recovery after a timeout error."""
    with patch(
        PATCH_READ_FRAME,
        side_effect=TimeoutError("No data"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_SERIAL_PORT: "/dev/ttyUSB0",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "timeout_connect"}

    # Recover: now the dongle responds (mock_serial_port fixture takes over)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
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
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_teleinfo")
async def test_user_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unexpected exceptions."""
    with patch(
        PATCH_READ_FRAME,
        side_effect=RuntimeError("unexpected"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_SERIAL_PORT: "/dev/ttyUSB0",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("mock_teleinfo")
async def test_user_flow_unknown_error_recovery(
    hass: HomeAssistant, mock_serial_port: MagicMock
) -> None:
    """Test recovery after an unknown error."""
    with patch(
        PATCH_READ_FRAME,
        side_effect=RuntimeError("unexpected"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_SERIAL_PORT: "/dev/ttyUSB0",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover (mock_serial_port fixture takes over)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_decode_error(
    hass: HomeAssistant, mock_teleinfo: MagicMock, mock_serial_port: MagicMock
) -> None:
    """Test we handle decode errors from pyteleinfo."""
    mock_teleinfo.decode.side_effect = mock_teleinfo.TeleinfoError("bad frame")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


# --- USB Discovery tests ---

PATCH_GET_SERIAL_BY_ID = (
    "homeassistant.components.teleinfo.config_flow.usb.get_serial_by_id"
)


@pytest.mark.usefixtures("mock_teleinfo")
async def test_usb_discovery_success(
    hass: HomeAssistant, mock_serial_port: MagicMock
) -> None:
    """Test USB discovery happy path: detect → validate → confirm → create entry."""

    with patch(PATCH_GET_SERIAL_BY_ID, side_effect=lambda x: x):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USB},
            data=USB_DISCOVERY_INFO,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Teleinfo (/dev/ttyUSB0)"

    config_entry = result["result"]
    assert config_entry.unique_id == "021861348497"
    assert config_entry.data == {
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
    }


@pytest.mark.usefixtures("mock_teleinfo")
async def test_usb_discovery_not_teleinfo(hass: HomeAssistant) -> None:
    """Test USB discovery aborts when frame read times out (not a Teleinfo device)."""

    with (
        patch(PATCH_GET_SERIAL_BY_ID, side_effect=lambda x: x),
        patch(
            PATCH_READ_FRAME,
            side_effect=TimeoutError("No data received"),
        ),
    ):
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

    with patch(PATCH_GET_SERIAL_BY_ID, return_value="/dev/ttyUSB-new"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USB},
            data=USB_DISCOVERY_INFO,
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

    with patch(PATCH_GET_SERIAL_BY_ID, side_effect=lambda x: x):
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

    with patch(PATCH_GET_SERIAL_BY_ID, side_effect=lambda x: x):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USB},
            data=USB_DISCOVERY_INFO,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_teleinfo_device"
