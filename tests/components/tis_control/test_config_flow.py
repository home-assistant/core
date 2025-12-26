"""Tests for the TIS Control config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.tis_control.const import DOMAIN
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_show_setup_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    # Initialize the config flow through the Home Assistant flow manager.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # The first step should be the user form.
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "flow_id" in result
    assert CONF_PORT in result["data_schema"].schema


async def test_valid_port(hass: HomeAssistant) -> None:
    """Test handling of valid port."""
    # Start the flow.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Patch async_setup_entry to ensure we don't start the actual integration logic.
    with patch(
        "homeassistant.components.tis_control.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test that the flow is aborted when an entry with the same port already exists."""
    # Create the first successful entry.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tis_control.async_setup_entry",
        return_value=True,
    ):
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
