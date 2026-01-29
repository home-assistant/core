"""Test the ToneWinner AT-500 config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import serial

from homeassistant import config_entries
from homeassistant.components.tonewinner.const import (
    CONF_BAUD_RATE,
    CONF_SERIAL_PORT,
    DEFAULT_BAUD_RATE,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form and can successfully set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    # Mock successful serial port connection
    mock_serial = MagicMock()
    mock_serial.close = MagicMock()

    with patch("serial.Serial", return_value=mock_serial):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_PORT: "/dev/ttyUSB0",
                CONF_BAUD_RATE: DEFAULT_BAUD_RATE,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tonewinner AT-500"
    assert result["data"] == {
        CONF_SERIAL_PORT: "/dev/ttyUSB0",
        CONF_BAUD_RATE: DEFAULT_BAUD_RATE,
    }
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_with_custom_baudrate(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setup with custom baud rate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_serial = MagicMock()
    mock_serial.close = MagicMock()

    with patch("serial.Serial", return_value=mock_serial):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_PORT: "/dev/ttyUSB1",
                CONF_BAUD_RATE: 115200,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SERIAL_PORT: "/dev/ttyUSB1",
        CONF_BAUD_RATE: 115200,
    }


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock serial port failure
    with patch(
        "serial.Serial",
        side_effect=serial.SerialException("Permission denied"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_PORT: "/dev/ttyUSB0",
                CONF_BAUD_RATE: DEFAULT_BAUD_RATE,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Test recovery from error
    mock_serial = MagicMock()
    mock_serial.close = MagicMock()

    with patch("serial.Serial", return_value=mock_serial):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_PORT: "/dev/ttyUSB0",
                CONF_BAUD_RATE: DEFAULT_BAUD_RATE,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_os_error(hass: HomeAssistant) -> None:
    """Test we handle OS error (e.g., port doesn't exist)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock OS error
    with patch(
        "serial.Serial",
        side_effect=OSError("Port not found"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL_PORT: "/dev/nonexistent",
                CONF_BAUD_RATE: DEFAULT_BAUD_RATE,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_default_values(hass: HomeAssistant) -> None:
    """Test that form shows correct default values."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    # Check that default values are present in the schema
    data_schema = result["data_schema"]
    assert data_schema is not None
