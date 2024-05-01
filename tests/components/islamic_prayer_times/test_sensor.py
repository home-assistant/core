"""The tests for the Islamic prayer times sensor platform."""

from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.components.islamic_prayer_times.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import NOW, PRAYER_TIMES, PRAYER_TIMES_TOMORROW, PRAYER_TIMES_YESTERDAY

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def set_utc(hass: HomeAssistant) -> None:
    """Set timezone to UTC."""
    hass.config.set_time_zone("UTC")


@pytest.mark.parametrize(
    ("key", "sensor_name"),
    [
        ("Fajr", "sensor.islamic_prayer_times_fajr_prayer"),
        ("Sunrise", "sensor.islamic_prayer_times_sunrise_time"),
        ("Dhuhr", "sensor.islamic_prayer_times_dhuhr_prayer"),
        ("Asr", "sensor.islamic_prayer_times_asr_prayer"),
        ("Maghrib", "sensor.islamic_prayer_times_maghrib_prayer"),
        ("Isha", "sensor.islamic_prayer_times_isha_prayer"),
        ("Midnight", "sensor.islamic_prayer_times_midnight_time"),
    ],
)
# In our example data, Islamic midnight occurs at 00:44 (yesterday's times, occurs today) and 00:45 (today's times, occurs tomorrow),
# hence we check that the times roll over at exactly the desired minute
@pytest.mark.parametrize(
    ("offset", "prayer_times"),
    [
        (timedelta(days=-1), PRAYER_TIMES_YESTERDAY),
        (timedelta(minutes=44), PRAYER_TIMES_YESTERDAY),
        (timedelta(minutes=44, seconds=1), PRAYER_TIMES),  # Rolls over at 00:44 + 1 sec
        (timedelta(days=1, minutes=45), PRAYER_TIMES),
        (
            timedelta(days=1, minutes=45, seconds=1),  # Rolls over at 00:45 + 1 sec
            PRAYER_TIMES_TOMORROW,
        ),
    ],
)
async def test_islamic_prayer_times_sensors(
    hass: HomeAssistant,
    key: str,
    sensor_name: str,
    offset: timedelta,
    prayer_times: dict[str, str],
) -> None:
    """Test minimum Islamic prayer times configuration."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    with (
        patch(
            "prayer_times_calculator_offline.PrayerTimesCalculator.fetch_prayer_times",
            side_effect=(PRAYER_TIMES_YESTERDAY, PRAYER_TIMES, PRAYER_TIMES_TOMORROW),
        ),
        freeze_time(NOW + offset),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(sensor_name).state == prayer_times[key]
