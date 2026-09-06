"""Test the Zonneplan integration setup."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from pyzonneplan import (
    Token,
    ZonneplanAuthenticationError,
    ZonneplanConnectionError,
    ZonneplanTimeoutError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        pytest.param(
            ZonneplanAuthenticationError("bad token"),
            ConfigEntryState.SETUP_ERROR,
            id="authentication_error",
        ),
        pytest.param(
            ZonneplanTimeoutError("timed out"),
            ConfigEntryState.SETUP_RETRY,
            id="timeout_error",
        ),
        pytest.param(
            ZonneplanConnectionError("boom"),
            ConfigEntryState.SETUP_RETRY,
            id="connection_error",
        ),
    ],
)
async def test_setup_entry_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test errors while fetching data mark the entry for retry."""
    mock_zonneplan_client.async_get_account.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_setup_entry_persists_rotated_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test a rotated refresh token is persisted to the config entry."""
    rotated_token = Token(
        access_token="rotated-access-token",
        refresh_token="rotated-refresh-token",
        expires_at=dt_util.utcnow() + timedelta(hours=1),
    )
    mock_zonneplan_client.token = rotated_token
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_TOKEN] == rotated_token.as_dict()
