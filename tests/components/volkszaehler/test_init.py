"""Tests for the Volkszaehler integration setup."""

from unittest.mock import AsyncMock

from volkszaehler.exceptions import VolkszaehlerApiConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test successful setup and unload of a config entry."""
    mock_api.return_value.data = {"rows": []}

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "existing-subentry-id" in mock_config_entry.runtime_data

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test setup retry when the API cannot be reached."""
    mock_api.return_value.get_data.side_effect = VolkszaehlerApiConnectionError()

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test setup retry when the API returns no data."""
    mock_api.return_value.data = None

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_without_middleware(
    hass: HomeAssistant,
    mock_config_entry_without_middleware: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test setup with middleware disabled."""
    mock_api.return_value.data = {"rows": []}

    mock_config_entry_without_middleware.add_to_hass(hass)
    assert await hass.config_entries.async_setup(
        mock_config_entry_without_middleware.entry_id
    )

    assert mock_api.call_args.kwargs["middleware"] is False
