"""Test the MTA sensor platform."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gtfs_realtime_feed: MagicMock,
) -> None:
    """Test the sensor entity."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.1_line_times_sq_42_st_n_direction_next_arrival")
    assert state is not None
    assert state.attributes["stop_id"] == "127N"
    assert "arrivals" in state.attributes
    assert len(state.attributes["arrivals"]) == 1
    assert state.attributes["arrivals"][0]["route"] == "1"
    assert state.attributes["arrivals"][0]["destination"] == "Van Cortlandt Park - 242 St"
