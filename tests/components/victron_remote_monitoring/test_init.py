"""Tests for Victron Remote Monitoring integration setup and auth handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from victron_vrm.exceptions import AuthenticationError, VictronVRMError

from homeassistant.components.victron_remote_monitoring.const import (
    CONF_API_TOKEN,
    CONF_SITE_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a config entry for tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_TOKEN: "token", CONF_SITE_ID: 123456},
        unique_id="123456",
        title="VRM for Test",
        version=1,
    )


@pytest.mark.parametrize(
    "side_effect",
    [
        AuthenticationError("bad", status_code=401),
        VictronVRMError("boom", status_code=500, response_data={}),
    ],
)
async def test_setup_auth_or_connection_error_starts_retry_or_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, side_effect: Exception
) -> None:
    """Auth errors initiate reauth flow; other errors set entry to retry.

    AuthenticationError should surface as ConfigEntryAuthFailed which marks the entry in SETUP_ERROR and starts a reauth flow.
    Generic VictronVRMError should set the entry to SETUP_RETRY without a reauth flow.
    """
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victron_remote_monitoring.coordinator.VictronVRMClient"
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.installations.stats = AsyncMock(side_effect=side_effect)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    if isinstance(side_effect, AuthenticationError):
        # Entry should be in error and a reauth flow should be active
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
        active_flows = mock_config_entry.async_get_active_flows(hass, {"reauth"})
        assert any(active_flows)
    else:
        # Connection/other API error -> retry state, no reauth flow
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
        active_flows = mock_config_entry.async_get_active_flows(hass, {"reauth"})
        assert not any(active_flows)
