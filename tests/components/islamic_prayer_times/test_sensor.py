"""The tests for the Islamic prayer times sensor platform."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components import islamic_prayer_times
from homeassistant.components.islamic_prayer_times.const import SENSOR_TYPES
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from . import (
    NEW_PRAYER_TIMES,
    NEW_PRAYER_TIMES_TIMESTAMPS,
    NOW,
    PRAYER_TIMES,
    PRAYER_TIMES_TIMESTAMPS,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_islamic_prayer_times_sensors(
    hass: HomeAssistant, legacy_patchable_time
) -> None:
    """Test minimum Islamic prayer times configuration."""
    entry = MockConfigEntry(domain=islamic_prayer_times.DOMAIN, data={})
    entry.add_to_hass(hass)

    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times"
    ) as FetchPrayerTimes, patch("homeassistant.util.dt.now", return_value=NOW):
        FetchPrayerTimes.side_effect = [
            PRAYER_TIMES,
            NEW_PRAYER_TIMES,
        ]
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        for prayer in SENSOR_TYPES:
            state = hass.states.get(f"sensor.{slugify(prayer.name)}")
            if state:
                assert (
                    state.state
                    == PRAYER_TIMES_TIMESTAMPS[prayer.key]
                    .astimezone(dt_util.UTC)
                    .isoformat()
                )
        midnight_sensor = hass.states.get("sensor.midnight_time")
        if midnight_sensor:
            midnight_time = dt_util.parse_datetime(midnight_sensor.state)
            if midnight_time:
                future = midnight_time + timedelta(days=1, minutes=1)

            async_fire_time_changed(hass, future)
            await hass.async_block_till_done()

            for prayer in SENSOR_TYPES:
                state = hass.states.get(f"sensor.{slugify(prayer.name)}")
                if state:
                    assert (
                        state.state
                        == NEW_PRAYER_TIMES_TIMESTAMPS[prayer.key]
                        .astimezone(dt_util.UTC)
                        .isoformat()
                    )
