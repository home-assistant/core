"""Tests for the ALLNET data update coordinator."""

from unittest.mock import patch

from allnet.exceptions import (
    AllnetAuthenticationError,
    AllnetConnectionError,
    AllnetInvalidResponseError,
)
import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "error_message", "reauth_calls"),
    [
        pytest.param(
            AllnetAuthenticationError("401"),
            "Authentication failed",
            1,
            id="auth",
        ),
        pytest.param(
            AllnetConnectionError("offline"), "Cannot connect", 0, id="connection"
        ),
        pytest.param(
            AllnetInvalidResponseError("invalid"),
            "Invalid API response",
            0,
            id="invalid",
        ),
    ],
)
async def test_coordinator_update_errors(
    hass: HomeAssistant,
    setup_integration: ConfigEntry,
    exception: Exception,
    error_message: str,
    reauth_calls: int,
) -> None:
    """Test coordinator turns client errors into update failures."""
    runtime = setup_integration.runtime_data
    runtime.client.async_get_channels.side_effect = exception

    with (
        patch.object(setup_integration, "async_start_reauth") as mock_reauth,
        pytest.raises(UpdateFailed, match=error_message),
    ):
        await runtime.coordinator._async_update_data()

    assert mock_reauth.call_count == reauth_calls
