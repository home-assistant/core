"""Test the Uhoo config flow."""

from unittest.mock import Mock

from aiohttp.client_exceptions import ClientConnectorDNSError
import pytest
from uhooapi.errors import UnauthorizedError

from homeassistant.components.uhoo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_uhoo_client,
    mock_setup_entry,
) -> None:
    """Test the full user flow from start to finish."""
    # Mock successful login
    mock_uhoo_client.login.return_value = None

    # Step 1: Initialize the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Step 2: Submit valid credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "valid-api-key-test12345"},
    )

    # Step 3: Verify entry creation
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "uHoo (12345)"  # Last 5 chars
    assert result["data"] == {CONF_API_KEY: "valid-api-key-test12345"}
    assert result["result"]

    # Verify setup was called
    mock_setup_entry.assert_called_once()


async def test_happy_flow(
    hass: HomeAssistant, mock_uhoo_client, mock_setup_entry
) -> None:
    """Test a complete user flow from start to finish with errors and success."""
    # Step 1: Initialize the flow ONCE and get the flow_id
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_uhoo_client.login.reset_mock()
    mock_uhoo_client.login.side_effect = None
    mock_uhoo_client.login.return_value = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "valid-api-key-12345"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "uHoo (12345)"
    assert result["data"] == {CONF_API_KEY: "valid-api-key-12345"}

    mock_setup_entry.assert_called_once()


async def test_form_duplicate_entry(
    hass: HomeAssistant, mock_uhoo_client, mock_uhoo_config_entry
) -> None:
    """Test duplicate entry aborts."""
    mock_uhoo_client.login.return_value = None
    mock_uhoo_config_entry.add_to_hass(hass)

    # Try to create duplicate
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "valid-api-key-12345"},  # Same API key
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error_type", "api_key", "should_retry"),
    [
        (ConnectionError("Cannot connect"), "invalid_auth", "api-key", True),
        (
            ClientConnectorDNSError(Mock(), OSError("DNS failure")),
            "invalid_auth",
            "api-key",
            True,
        ),
        (
            UnauthorizedError("Invalid credentials"),
            "invalid_auth",
            "invalid-api-key",
            False,
        ),
    ],
)
async def test_form_client_exceptions(
    hass: HomeAssistant,
    mock_uhoo_client,
    exception,
    error_type,
    api_key,
    should_retry,
) -> None:
    """Test form when client raises various exceptions."""
    if should_retry:
        # Set exception for first call, success for retry
        mock_uhoo_client.login.side_effect = [exception, None]
    else:
        # Only test the error case (no retry)
        mock_uhoo_client.login.side_effect = exception

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Submit API key
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: api_key},
    )

    # Should show form with error
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_type}

    # Verify login was called
    mock_uhoo_client.login.assert_called_once()

    if should_retry:
        # Clear mock and retry
        mock_uhoo_client.login.reset_mock()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: api_key},
        )

        # Should create entry
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_connection_error(hass: HomeAssistant, mock_uhoo_client) -> None:
    """Test DNS connection error during login."""
    # Create a ClientConnectorDNSError
    mock_uhoo_client.login.side_effect = ClientConnectorDNSError(
        ConnectionError("Cannot connect"), OSError("DNS failure")
    )
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    # Submit API key
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "api-key"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}
    mock_uhoo_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "api-key"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
