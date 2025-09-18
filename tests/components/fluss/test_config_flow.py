"""Tests for the Fluss+ integration's config flow."""

from __future__ import annotations

from typing import Any
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
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def config_flow(hass: HomeAssistant) -> FlussConfigFlow:
    """Fixture to create a FlussConfigFlow instance with hass."""
    flow = FlussConfigFlow()
    flow.hass = hass
    return flow


async def test_step_user_initial_form(hass: HomeAssistant) -> None:
    """Test initial form display when no user input is provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"] is STEP_USER_DATA_SCHEMA
    assert result["errors"] == {}


async def test_step_user_success(hass: HomeAssistant) -> None:
    """Test successful user step."""
    user_input: dict[str, Any] = {CONF_API_KEY: "valid_api_key"}

    with patch("fluss_api.FlussApiClient") as mock_client:
        mock_client.return_value = None
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Fluss+ Devices"
    assert result["data"] == user_input


async def test_step_user_invalid_input(hass: HomeAssistant) -> None:
    """Test invalid user input (e.g., missing API key)."""
    with pytest.raises(vol.Invalid):
        STEP_USER_DATA_SCHEMA({})  # Missing required key


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (FlussApiClientAuthenticationError, "invalid_auth"),
        (FlussApiClientCommunicationError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_step_user_errors(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test error cases for user step with recovery."""
    user_input: dict[str, Any] = {CONF_API_KEY: "some_api_key"}

    with patch(
        "fluss_api.FlussApiClient",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


async def test_abort_if_already_configured(hass: HomeAssistant) -> None:
    """Test abort if unique ID is already configured."""
    user_input: dict[str, Any] = {CONF_API_KEY: "existing_key"}

    # Simulate existing entry
    with patch.object(hass.config_entries, "async_entries", return_value=[True]):
        with patch("fluss_api.FlussApiClient") as mock_client:
            mock_client.return_value = None
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}, data=user_input
            )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that only one instance is allowed."""
    with patch(
        "homeassistant.components.fluss.config_flow.FlussConfigFlow._async_has_devices",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"