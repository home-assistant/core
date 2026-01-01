"""Tests for the TIS Control config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.tis_control.const import DOMAIN
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# Define the path to patch TISApi based on where it is used in config_flow.py
PATCH_TIS_API = "homeassistant.components.tis_control.config_flow.TISApi"


async def test_show_setup_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "flow_id" in result
    assert CONF_PORT in result["data_schema"].schema


async def test_valid_port(hass: HomeAssistant) -> None:
    """Test handling of valid port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # We must patch TISApi to simulate a successful connection
    # and patch async_setup_entry to stop the integration from starting.
    with (
        patch(PATCH_TIS_API) as mock_tis_api,
        patch(
            "homeassistant.components.tis_control.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        # Configure the mock to simulate a successful connect
        mock_instance = mock_tis_api.return_value
        mock_instance.connect = AsyncMock(return_value=True)

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PORT: 1234},
        )
        await hass.async_block_till_done()

    # The flow should create a new config entry.
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TIS Control Bridge"
    assert result2["data"] == {CONF_PORT: 1234}

    # Ensure the setup function was called.
    assert len(mock_setup_entry.mock_calls) == 1
    # Ensure connect was called once
    assert len(mock_instance.connect.mock_calls) == 1


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test handling of connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(PATCH_TIS_API) as mock_tis_api:
        # Configure the mock to raise ConnectionError when connect is called
        mock_instance = mock_tis_api.return_value
        mock_instance.connect = AsyncMock(side_effect=ConnectionError("Boom"))

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PORT: 6000},
        )
        await hass.async_block_till_done()

    # The flow should show the form again with an error.
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test that the flow is aborted when an entry with the same port already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # We need to mock success for the first entry creation
    with (
        patch(PATCH_TIS_API) as mock_tis_api,
        patch(
            "homeassistant.components.tis_control.async_setup_entry",
            return_value=True,
        ),
    ):
        mock_instance = mock_tis_api.return_value
        mock_instance.connect = AsyncMock(return_value=True)

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

    # Note: connect() is not called for the second attempt because
    # _abort_if_unique_id_configured happens BEFORE validate_input
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={CONF_PORT: 6000},
    )
    await hass.async_block_till_done()

    # Verify that the second flow is aborted.
    assert result4["type"] == FlowResultType.ABORT
    assert result4["reason"] == "already_configured"
