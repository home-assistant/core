"""Tests for the TIS Control config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.tis_control.config_flow import TISConfigFlow
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


async def test_invalid_port(hass: HomeAssistant) -> None:
    """Test handling of invalid port."""
    # Start the flow.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Patch the validate_port method on the class, not an instance.
    with patch(
        "homeassistant.components.tis_control.config_flow.TISConfigFlow.validate_port",
        return_value=False,
    ):
        # Configure the flow with the user's input.
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PORT: 99999},
        )
        await hass.async_block_till_done()

    # The flow should show the form again with an error.
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_port"}


async def test_valid_port(hass: HomeAssistant) -> None:
    """Test handling of valid port."""
    # Start the flow.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Patch validate_port and the async_setup_entry to prevent real setup.
    with (
        patch(
            "homeassistant.components.tis_control.config_flow.TISConfigFlow.validate_port",
            return_value=True,
        ),
        patch(
            "homeassistant.components.tis_control.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        # Configure the flow with valid user input.
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
    # Step 1: Create the first successful entry.
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

    # Step 2: Try to create a second entry with the same port.
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


async def test_validate_port() -> None:
    """Test the validate_port method directly."""
    config_flow = TISConfigFlow()

    assert await config_flow.validate_port(1234) is True
    assert await config_flow.validate_port(0) is False
    assert await config_flow.validate_port(65536) is False
    assert await config_flow.validate_port("invalid") is False  # type: ignore noqa: PGH003
