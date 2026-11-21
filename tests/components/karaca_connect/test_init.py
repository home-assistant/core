"""Tests for the Karaca Connect config entry lifecycle."""

from unittest.mock import AsyncMock

from karaca_connect_client import KaracaAuthError, KaracaConnectionError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_karaca_client: AsyncMock,
) -> None:
    """Set up and unload the status sensor."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_karaca_client.get_detail.assert_awaited()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_setup_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_karaca_client: AsyncMock,
) -> None:
    """Authentication failure should fail entry setup cleanly."""
    mock_karaca_client.login.side_effect = KaracaAuthError()
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_karaca_client: AsyncMock,
) -> None:
    """Cloud errors should make setup retryable."""
    mock_karaca_client.get_detail.side_effect = KaracaConnectionError()
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
