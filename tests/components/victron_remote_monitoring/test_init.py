"""Tests for Victron Remote Monitoring integration setup and auth handling."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from victron_vrm.exceptions import AuthenticationError, VictronVRMError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "side_effect",
    [
        AuthenticationError("bad", status_code=401),
        VictronVRMError("boom", status_code=500, response_data={}),
    ],
)
async def test_setup_auth_or_connection_error_starts_retry_or_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vrm_client,  # provided by shared conftest
    side_effect: Exception,
) -> None:
    """Auth errors initiate reauth flow; other errors set entry to retry.

    AuthenticationError should surface as ConfigEntryAuthFailed which marks the entry in SETUP_ERROR and starts a reauth flow.
    Generic VictronVRMError should set the entry to SETUP_RETRY without a reauth flow.
    """
    mock_config_entry.add_to_hass(hass)
    # Override default success behaviour of fixture to raise side effect
    mock_vrm_client.installations.stats.side_effect = side_effect

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


async def test_options_update_triggers_reload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_vrm_client
) -> None:
    """Test that updating options causes the entry to reload (covers async_update_options)."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Spy on reload method of config entries
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as wrapped_reload:
        hass.config_entries.async_update_entry(
            mock_config_entry, options={"dummy": True}
        )
        await hass.async_block_till_done()
        assert wrapped_reload.call_count == 1
