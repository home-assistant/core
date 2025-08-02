"""Test the World Air Quality Index (WAQI) initialization."""

from unittest.mock import AsyncMock

from aiowaqi import WAQIError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waqi: AsyncMock,
) -> None:
    """Test setup failure due to API error."""
    mock_waqi.get_by_station_number.side_effect = WAQIError("API error")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
