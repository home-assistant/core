"""Test Hydrawise sensor."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.hydrawise.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.freeze_time("2023-10-01 00:00:00+00:00")
async def test_states(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor states."""
    # Make the coordinator refresh data.
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    watering_time1 = hass.states.get("sensor.zone_one_watering_time")
    assert watering_time1 is not None
    assert watering_time1.state == "0"

    watering_time2 = hass.states.get("sensor.zone_two_watering_time")
    assert watering_time2 is not None
    assert watering_time2.state == "29"

    next_cycle = hass.states.get("sensor.zone_one_next_cycle")
    assert next_cycle is not None
    assert next_cycle.state == "2023-10-04T19:52:27+00:00"
