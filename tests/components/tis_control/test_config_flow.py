"""Tests for the TIS Control config flow."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant import config_entries
from homeassistant.components.tis_control.const import DOMAIN
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_show_setup_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "flow_id" in result
    assert CONF_PORT in result["data_schema"].schema


async def test_valid_port(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_tis_api: MagicMock
) -> None:
    """Test handling of valid port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PORT: 1234},
    )
    await hass.async_block_till_done()

    # The flow should create a new config entry.
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TIS Control Bridge"
    assert result2["data"] == {CONF_PORT: 1234}

    # Ensure the setup function and connect were called.
    mock_setup_entry.assert_called_once()
    mock_tis_api.connect.assert_awaited_once()


async def test_connection_error(hass: HomeAssistant, mock_tis_api: MagicMock) -> None:
    """Test handling of connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Configure the mock to raise an error specifically for this test
    mock_tis_api.connect.side_effect = ConnectionError("Boom")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PORT: 6000},
    )
    await hass.async_block_till_done()

    # The flow should show the form again with an error.
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_duplicate_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_tis_api: MagicMock
) -> None:
    """Test that the flow is aborted when an entry with the same port already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PORT: 6000},
    )
    await hass.async_block_till_done()

    # Verify the first entry was created.
    assert result2["type"] == FlowResultType.CREATE_ENTRY

    # Try to create a second entry with the same port.
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={CONF_PORT: 6000},
    )
    await hass.async_block_till_done()

    # Verify that the second flow is aborted.
    assert result4["type"] == FlowResultType.ABORT
    assert result4["reason"] == "already_configured"


async def test_unexpected_exception(
    hass: HomeAssistant, mock_tis_api: MagicMock
) -> None:
    """Test handling of an unexpected exception during validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Force a generic Exception that isn't caught by the specific ConnectionError handler
    mock_tis_api.connect.side_effect = Exception("Unexpected")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PORT: 6000},
    )
    await hass.async_block_till_done()

    # The flow should still show the form with the error because it returns False
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
