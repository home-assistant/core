"""Test the coordinator provided by the Autarco integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from autarco import AutarcoConnectionError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_update_failed(
    hass: HomeAssistant,
    mock_autarco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator throws UpdateFailed after failed update."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_autarco_client.get_solar.side_effect = AutarcoConnectionError
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
