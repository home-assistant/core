"""Tests for the Aruba ClearPass (cppm_tracker) integration setup."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
import requests

from homeassistant.components.cppm_tracker.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("side_effect", "access_token"),
    [
        pytest.param(requests.exceptions.ConnectionError, "token", id="cannot_connect"),
        pytest.param(KeyError("access_token"), "token", id="rejected"),
        pytest.param(None, None, id="no_token"),
    ],
)
async def test_setup_retry_on_login_failure(
    hass: HomeAssistant,
    mock_clearpass: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception | None,
    access_token: str | None,
) -> None:
    """Test the config entry retries setup when login fails."""
    mock_clearpass.side_effect = side_effect
    mock_clearpass.return_value.access_token = access_token

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_on_query_error(
    hass: HomeAssistant, mock_clearpass: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry retries setup when the endpoint query fails."""
    mock_clearpass.return_value.get_endpoints.side_effect = KeyError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_client_authenticates_once(
    hass: HomeAssistant,
    mock_clearpass: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the ClearPass client logs in once and is reused across updates."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_clearpass.call_count == 1
    assert mock_clearpass.return_value.get_endpoints.call_count == 2


async def test_unload_entry(
    hass: HomeAssistant, mock_clearpass: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
