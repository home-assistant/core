"""Test the Actron Air coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from actron_neo_api import ActronAirAPIError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_setup import FrozenDateTimeFactory


async def test_coordinator_update_general_error(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles general errors gracefully."""
    # Setup integration first
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Now make the update fail with API error
    mock_actron_api.update_status = AsyncMock(
        side_effect=ActronAirAPIError("Connection error")
    )

    # Use freezer.tick to advance time and trigger update
    freezer.tick(timedelta(seconds=31))
    await hass.async_block_till_done()
    await (
        hass.async_block_till_done()
    )  # Extra wait to ensure entity state updates propagate
    # Config entry should still be loaded (UpdateFailed doesn't change entry state)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Entities attached to the coordinator should be unavailable
    entities = hass.states.async_entity_ids()
    for entity_id in entities:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
