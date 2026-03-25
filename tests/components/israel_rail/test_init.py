"""Test init of israel_rail integration."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry


async def test_invalid_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_israelrail: AsyncMock,
) -> None:
    """Ensure nothing is created when config is wrong."""
    mock_israelrail.query.side_effect = Exception("error")
    await init_integration(hass, mock_config_entry)
    assert not hass.states.async_entity_ids("sensor")
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
