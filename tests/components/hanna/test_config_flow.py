"""Tests for the Hanna Instruments integration config flow."""

from unittest.mock import AsyncMock, MagicMock

from hanna_cloud import AuthenticationError
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout

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


async def _test_error_scenario(
    hass: HomeAssistant,
    mock_hanna_client: MagicMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test a specific error scenario in the config flow."""
    mock_hanna_client.authenticate.side_effect = exception

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
    assert result["errors"] == {"base": expected_error}


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

    await _test_error_scenario(hass, mock_hanna_client, auth_error, "invalid_auth")


async def test_cannot_connect_timeout(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hanna_client: MagicMock,
) -> None:
    """Test connection timeout error."""
    await _test_error_scenario(
        hass, mock_hanna_client, Timeout("Connection timeout"), "cannot_connect"
    )


async def test_cannot_connect_connection_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hanna_client: MagicMock,
) -> None:
    """Test connection error."""
    await _test_error_scenario(
        hass,
        mock_hanna_client,
        RequestsConnectionError("Connection failed"),
        "cannot_connect",
    )
