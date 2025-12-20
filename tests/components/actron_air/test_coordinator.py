"""Test the Actron Air coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun import freeze_time

from homeassistant.components.actron_air.coordinator import STALE_DEVICE_TIMEOUT
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry


@freeze_time("2025-01-01 12:00:00")
async def test_coordinator_is_device_stale_true(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test is_device_stale returns True when device is stale."""
    # Setup integration
    await setup_integration(hass, mock_config_entry)

    # Get the coordinator from runtime_data
    coordinator = mock_config_entry.runtime_data.system_coordinators["123456"]

    # Manually set last_seen to more than STALE_DEVICE_TIMEOUT ago
    coordinator.last_seen = (
        dt_util.utcnow() - STALE_DEVICE_TIMEOUT - timedelta(seconds=1)
    )

    # Device should now be stale
    assert coordinator.is_device_stale()

    # Trigger entity state updates to reflect the stale device status
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    # Entities attached to the coordinator should be unavailable
    entities = hass.states.async_entity_ids()
    for entity_id in entities:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
