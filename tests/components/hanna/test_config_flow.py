"""Tests for the Hanna Instruments integration config flow."""

from unittest.mock import AsyncMock, MagicMock

from hanna_cloud import AuthenticationError

from homeassistant.components.hanna.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hanna_client: MagicMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "test@example.com",
            "password": "test-password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == {
        "email": "test@example.com",
        "password": "test-password",
    }


async def test_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hanna_client: MagicMock,
) -> None:
    """Test invalid authentication."""
    # Create a RequestException with 401 status code to simulate authentication failure
    auth_error = AuthenticationError("Authentication failed")
    auth_error.response = MagicMock()
    auth_error.response.status_code = 401

    mock_hanna_client.authenticate.side_effect = auth_error

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"email": "test@example.com", "password": "test-password"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}
