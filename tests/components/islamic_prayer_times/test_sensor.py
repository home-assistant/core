"""The tests for the Islamic prayer times sensor platform."""
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.components.islamic_prayer_times.const import DOMAIN
from homeassistant.components.islamic_prayer_times.sensor import SENSOR_TYPES
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from . import NOW, PRAYER_TIMES, PRAYER_TIMES_TIMESTAMPS

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def set_utc(hass: HomeAssistant) -> None:
    """Set timezone to UTC."""
    hass.config.set_time_zone("UTC")


async def test_islamic_prayer_times_sensors(hass: HomeAssistant) -> None:
    """Test minimum Islamic prayer times configuration."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ), freeze_time(NOW):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        for prayer in SENSOR_TYPES:
            assert (
                hass.states.get(f"sensor.{DOMAIN}_{slugify(prayer.name)}").state
                == PRAYER_TIMES_TIMESTAMPS[prayer.key]
                .astimezone(dt_util.UTC)
                .isoformat()
            )
