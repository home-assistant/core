"""Tests for Victron Remote Monitoring integration setup and auth handling."""

from __future__ import annotations

import pytest
from victron_vrm.exceptions import AuthenticationError, VictronVRMError

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expects_reauth"),
    [
        (
            AuthenticationError("bad", status_code=401),
            ConfigEntryState.SETUP_ERROR,
            True,
        ),
        (
            VictronVRMError("boom", status_code=500, response_data={}),
            ConfigEntryState.SETUP_RETRY,
            False,
        ),
    ],
)
async def test_setup_auth_or_connection_error_starts_retry_or_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vrm_client,
    side_effect: Exception | None,
    expected_state: ConfigEntryState,
    expects_reauth: bool,
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

    assert mock_config_entry.state is expected_state
    flows_list = list(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    assert bool(flows_list) is expects_reauth
