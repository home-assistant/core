"""Test the EvolvIOT integration setup."""

from unittest.mock import AsyncMock, patch

from pyevolviot import EvolvIOTConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_connect_websocket: AsyncMock,
) -> None:
    """Test setting up a config entry."""
    assert setup_integration.state is ConfigEntryState.LOADED
    mock_connect_websocket.assert_awaited_once()


async def test_unload_entry(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_websocket,
) -> None:
    """Test unloading a config entry."""
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert mock_websocket.closed


async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test connection failure during setup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "pyevolviot.EvolvIOTApi.async_connect_websocket",
        side_effect=EvolvIOTConnectionError,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
