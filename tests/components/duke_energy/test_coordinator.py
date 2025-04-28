"""Tests for the SolarEdge coordinator services."""

from datetime import timedelta
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.recorder import Recorder
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_with_meters: Mock,
    freezer: FrozenDateTimeFactory,
    recorder_mock: Recorder,
) -> None:
    """Test Coordinator."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_api_with_meters.get_meters.call_count == 1
    # 3 years of data
    assert mock_api_with_meters.get_energy_usage.call_count == 37

    with patch(
        "homeassistant.components.duke_energy.coordinator.get_last_statistics",
        return_value={
            "duke_energy:electric_123_energy_consumption": [
                {"start": dt_util.now().timestamp()}
            ]
        },
    ):
        freezer.tick(timedelta(hours=12))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert mock_api_with_meters.get_meters.call_count == 2
        # Now have stats, so only one call
        assert mock_api_with_meters.get_energy_usage.call_count == 38
