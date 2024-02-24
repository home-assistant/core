"""The tests for the Islamic prayer times sensor platform."""
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.components.islamic_prayer_times.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import NOW, PRAYER_TIMES

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
async def test_islamic_prayer_times_sensors(
    hass: HomeAssistant, key: str, sensor_name: str
) -> None:
    """Test minimum Islamic prayer times configuration."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ), freeze_time(NOW):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(sensor_name).state == PRAYER_TIMES[key]
