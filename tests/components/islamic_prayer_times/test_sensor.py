"""The tests for the Islamic prayer times sensor platform."""
from unittest.mock import patch

from homeassistant.components import islamic_prayer_times

from tests.common import MockConfigEntry

LATITUDE = 41
LONGITUDE = -87
CALC_METHOD = "isna"
ENTITY_ID_FORMAT = "sensor.islamic_prayer_time_{}"

MOCK_OPTIONS = {islamic_prayer_times.CONF_CALC_METHOD: "makkah"}

PRAYER_TIMES = {
    "Fajr": "06:10",
    "Sunrise": "07:25",
    "Dhuhr": "12:30",
    "Asr": "15:32",
    "Maghrib": "17:35",
    "Isha": "18:53",
    "Midnight": "00:45",
}


async def test_islamic_prayer_times_sensors(hass):
    """Test minimum Islamic prayer times configuration."""
    min_config_sensors = [
        "fajr",
        "sunrise",
        "dhuhr",
        "asr",
        "maghrib",
        "isha",
        "midnight",
    ]

    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ):
        config_entry = MockConfigEntry(
            domain=islamic_prayer_times.DOMAIN, data={}, options=MOCK_OPTIONS
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        for sensor in min_config_sensors:
            entity_id = ENTITY_ID_FORMAT.format(sensor)
            entity_id_name = sensor.capitalize()
            pt_dt = hass.data[islamic_prayer_times.DOMAIN].get_prayer_time_as_dt(
                PRAYER_TIMES[entity_id_name]
            )
            state = hass.states.get(entity_id)
            assert state.state == pt_dt.isoformat()
            assert state.name == entity_id_name
