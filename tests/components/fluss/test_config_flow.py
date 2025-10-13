"""Tests for the Fluss+ config flow."""

from unittest.mock import AsyncMock, patch

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
)
import pytest

from homeassistant.components.fluss.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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
    user_input = {CONF_API_KEY: "some_api_key"}

    # Mock FlussApiClient to raise the specified exception
    with patch(
        "homeassistant.components.fluss.config_flow.FlussApiClient",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=user_input
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": expected_error}

    # Test recovery by removing the side_effect
    with patch(
        "homeassistant.components.fluss.config_flow.FlussApiClient",
        return_value=AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "My Fluss+ Devices"
        assert result["data"] == user_input
