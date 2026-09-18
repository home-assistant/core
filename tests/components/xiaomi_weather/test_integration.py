"""Test Xiaomi Weather configuration-entry setup."""

from unittest.mock import AsyncMock

from homeassistant.components.xiaomi_weather.api import XiaomiWeatherError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_retry(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    """Test setup retry."""
    client.side_effect = XiaomiWeatherError
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
