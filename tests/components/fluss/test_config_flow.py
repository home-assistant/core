"""Tests for the Fluss integration's config flow."""

from unittest.mock import patch

from fluss_api import (
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
)
import pytest

from homeassistant.components.fluss.config_flow import FlussConfigFlow


@pytest.fixture
def config_flow():
    """Fixture to create a FlussConfigFlow instance."""
    return FlussConfigFlow()


async def test_step_user_success(config_flow):
    """Test successful user step."""
    user_input = {"api_key": "valid_api_key"}

    with patch(
        "homeassistant.components.fluss.config_flow.FlussApiClient"
    ) as mock_client:
        mock_client.return_value = None  # Simulate successful client creation

        result = await config_flow.async_step_user(user_input)

    assert result["type"] == "create_entry"
    assert result["title"] == "Fluss Device"
    assert result["data"] == user_input


async def test_step_user_invalid_auth(config_flow):
    """Test invalid authentication."""
    user_input = {"api_key": "invalid_api_key"}

    with patch(
        "homeassistant.components.fluss.config_flow.FlussApiClient"
    ) as mock_client:
        mock_client.side_effect = (
            FlussApiClientAuthenticationError  # Simulate invalid authentication
        )

        result = await config_flow.async_step_user(user_input)

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_step_user_cannot_connect(config_flow):
    """Test connection failure."""
    user_input = {"api_key": "some_api_key"}

    with patch(
        "homeassistant.components.fluss.config_flow.FlussApiClient"
    ) as mock_client:
        mock_client.side_effect = (
            FlussApiClientCommunicationError  # Simulate communication error
        )

        result = await config_flow.async_step_user(user_input)

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_step_user_unexpected_error(config_flow) -> None:
    """Test unexpected exception handling."""
    user_input = {"api_key": "some_api_key"}

    with patch(
        "homeassistant.components.fluss.config_flow.FlussApiClient"
    ) as mock_client:
        mock_client.side_effect = Exception(
            "Unexpected error"
        )  # Simulate unexpected error

        result = await config_flow.async_step_user(user_input)

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}
