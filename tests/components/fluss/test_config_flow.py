"""Tests for the Fluss+ integration's config flow."""

from unittest.mock import patch

from fluss_api import (
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
)
import pytest
import voluptuous as vol

from homeassistant.components.fluss.config_flow import (
    STEP_USER_DATA_SCHEMA,
    FlussConfigFlow,
)
from homeassistant.components.fluss.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def config_flow(hass):
    """Fixture to create a FlussConfigFlow instance with hass."""
    flow = FlussConfigFlow()
    flow.hass = hass
    return flow


async def test_step_user_initial_form(hass) -> None:
    """Test initial form display when no user input is provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"] == STEP_USER_DATA_SCHEMA
    assert result["errors"] == {}


async def test_step_user_success(hass) -> None:
    """Test successful user step."""
    user_input = {CONF_API_KEY: "valid_api_key"}

    with patch("homeassistant.components.fluss.config_flow.FlussApiClient") as mock_client:
        mock_client.return_value = None
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Fluss+ Devices"
    assert result["data"] == user_input


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (FlussApiClientAuthenticationError, "invalid_auth"),
        (FlussApiClientCommunicationError, "cannot_connect"),
    ],
)
async def test_step_user_errors(hass, exception, expected_error) -> None:
    """Test error cases for user step (invalid auth and connection failure)."""
    user_input = {CONF_API_KEY: "some_api_key"}

    with patch("homeassistant.components.fluss.config_flow.FlussApiClient") as mock_client:
        mock_client.side_effect = exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


async def test_step_user_unexpected_error(hass, caplog) -> None:
    """Test unexpected exception handling with logging."""
    user_input = {CONF_API_KEY: "some_api_key"}

    with patch("homeassistant.components.fluss.config_flow.FlussApiClient") as mock_client:
        mock_client.side_effect = Exception("Unexpected error")
        with caplog.at_level("ERROR"):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data=user_input
            )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}
    assert "Unexpected exception occurred" in caplog.text


async def test_single_instance_allowed(hass) -> None:
    """Test that only one instance is allowed."""
    with patch(
        "homeassistant.components.fluss.config_flow.FlussConfigFlow._async_current_entries",
        return_value=[True]
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
