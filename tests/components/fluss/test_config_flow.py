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
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def config_flow(hass):
    """Fixture to create a FlussConfigFlow instance with hass."""
    flow = FlussConfigFlow()
    flow.hass = hass
    return flow


async def test_step_user_initial_form(config_flow: FlussConfigFlow) -> None:
    """Test initial form display when no user input is provided."""
    result = await config_flow.async_step_user(user_input=None)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"] == STEP_USER_DATA_SCHEMA
    assert result["errors"] == {}


async def test_step_user_success(config_flow: FlussConfigFlow) -> None:
    """Test successful user step."""
    user_input = {CONF_API_KEY: "valid_api_key"}

    with patch("homeassistant.components.fluss.config_flow.FlussApiClient") as mock_client:
        mock_client.return_value = None
        result = await config_flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Fluss+ Devices"
    assert result["data"] == user_input


async def test_step_user_invalid_auth(config_flow: FlussConfigFlow) -> None:
    """Test invalid authentication."""
    user_input = {CONF_API_KEY: "invalid_api_key"}

    with patch("homeassistant.components.fluss.config_flow.FlussApiClient") as mock_client:
        mock_client.side_effect = FlussApiClientAuthenticationError
        result = await config_flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_step_user_cannot_connect(config_flow: FlussConfigFlow) -> None:
    """Test connection failure."""
    user_input = {CONF_API_KEY: "some_api_key"}

    with patch("homeassistant.components.fluss.config_flow.FlussApiClient") as mock_client:
        mock_client.side_effect = FlussApiClientCommunicationError
        result = await config_flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_step_user_unexpected_error(config_flow: FlussConfigFlow, caplog) -> None:
    """Test unexpected exception handling with logging."""
    user_input = {CONF_API_KEY: "some_api_key"}

    with patch("homeassistant.components.fluss.config_flow.FlussApiClient") as mock_client:
        mock_client.side_effect = Exception("Unexpected error")
        with caplog.at_level("ERROR"):
            result = await config_flow.async_step_user(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}
    assert "Unexpected exception occurred" in caplog.text


async def test_single_instance_allowed(config_flow: FlussConfigFlow) -> None:
    """Test that only one instance is allowed."""
    with patch.object(config_flow, "_async_current_entries", return_value=[True]):
        result = await config_flow.async_step_user(None)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


def test_data_schema_validation():
    """Test that the data schema enforces required string field."""
    # Valid input
    STEP_USER_DATA_SCHEMA({CONF_API_KEY: "test_key"})

    # Missing key
    with pytest.raises(vol.error.MultipleInvalid):
        STEP_USER_DATA_SCHEMA({})

    # Non-string value
    with pytest.raises(vol.error.MultipleInvalid):
        STEP_USER_DATA_SCHEMA({CONF_API_KEY: 123})
