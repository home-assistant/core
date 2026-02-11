"""Test the Hypontech Cloud init."""

from unittest.mock import AsyncMock, patch

from hyponcloud import AuthenticationError, RequestError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_timeout(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup entry with timeout error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hypontech.HyponCloud.connect",
        side_effect=TimeoutError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_authentication_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup entry with authentication error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hypontech.HyponCloud.connect",
        side_effect=AuthenticationError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup entry with connection error during data fetch."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.hypontech.HyponCloud.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hypontech.coordinator.HyponCloud.get_overview",
            side_effect=RequestError,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hyponcloud: AsyncMock,
) -> None:
    """Test setup and unload of config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
