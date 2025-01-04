"""Test the DVS Portal config flow."""

from unittest.mock import AsyncMock, patch

from dvsportal import DVSPortalAuthError
import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.asyncio

# Mocked valid user input
VALID_USER_INPUT = {
    CONF_HOST: "test-host",
    CONF_USERNAME: "test-user",
    CONF_PASSWORD: "test-pass",
    "user_agent": "HomeAssistant",
}


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid authentication during user config flow."""
    with patch(
        "homeassistant.components.dvsportal.config_flow.DVSPortal.token",
        side_effect=DVSPortalAuthError,
    ) as mock_token:
        # Step 1: Start the config flow
        result = await hass.config_entries.flow.async_init(
            "dvsportal", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # Step 2: Attempt to configure with invalid auth
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_USER_INPUT
        )

        # Ensure all tasks have completed
        await hass.async_block_till_done()

        # Step 3: Validate the result
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

        # Step 4: Ensure proper mock behavior
        mock_token.assert_called_once()


async def test_form(hass: HomeAssistant) -> None:
    """Test that form shows up."""

    # Step 1: Initialize the config flow
    result1 = await hass.config_entries.flow.async_init(
        "dvsportal", context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "user"
    assert result1["errors"] == {}

    # Step 2: Configure the flow with valid input
    with (
        patch(
            "homeassistant.components.dvsportal.config_flow.DVSPortal.token",
            new=AsyncMock(return_value=None),
        ) as mock_token,
        patch(
            "homeassistant.components.dvsportal.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            VALID_USER_INPUT,
        )
        await hass.async_block_till_done()
        mock_setup_entry.assert_called_once()
        mock_token.assert_called_once()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == VALID_USER_INPUT[CONF_USERNAME]
    assert result2["data"] == VALID_USER_INPUT

    # Step 3: Test Duplicate Config Flow
    result3 = await hass.config_entries.flow.async_init(
        "dvsportal", context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.dvsportal.config_flow.DVSPortal.token",
        new=AsyncMock(return_value=None),
    ) as mock_token:
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            VALID_USER_INPUT,
        )

    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "already_configured"
