"""Test the lg_soundbar setup."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

ENTITY_ID = "media_player.127_0_0_1"


async def test_setup_while_device_is_unreachable(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an unplugged soundbar does not prevent the setup."""
    mock_client.connected = False

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.start.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_unload(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading stops the client."""
    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.stop.assert_awaited_once()
