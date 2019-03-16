"""The tests for the Islamic prayer times sensor platform."""
from datetime import datetime, timedelta
from unittest.mock import patch
from homeassistant.setup import async_setup_component
from homeassistant.components.sensor.islamic_prayer_times import \
    IslamicPrayerTimesData
from tests.common import MockDependency
import homeassistant.util.dt as dt_util
from tests.common import async_fire_time_changed

LATITUDE = 41
LONGITUDE = -87
CALC_METHOD = 'isna'
PRAYER_TIMES = {"Fajr": "06:10", "Sunrise": "07:25", "Dhuhr": "12:30",
                "Asr": "15:32", "Maghrib": "17:35", "Isha": "18:53",
                "Midnight": "00:45"}
ENTITY_ID_FORMAT = 'sensor.islamic_prayer_time_{}'


def get_prayer_time_as_dt(prayer_time):
    """Create a datetime object for the respective prayer time."""
    today = datetime.today().strftime('%Y-%m-%d')
    date_time_str = '{} {}'.format(str(today), prayer_time)
    pt_dt = dt_util.parse_datetime(date_time_str)
    return pt_dt


async def test_islamic_prayer_times_min_config(hass):
    """Test minimum Islamic prayer times configuration."""
    min_config_sensors = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha']

    with MockDependency('prayer_times_calculator') as mock_pt_calc:
        mock_pt_calc.PrayerTimesCalculator.return_value.fetch_prayer_times \
            .return_value = PRAYER_TIMES

        config = {
            'sensor': {
                'platform': 'islamic_prayer_times'
            }
        }
        assert await async_setup_component(hass, 'sensor', config) is True

        for sensor in min_config_sensors:
            entity_id = ENTITY_ID_FORMAT.format(sensor)
            entity_id_name = sensor.capitalize()
            pt_dt = get_prayer_time_as_dt(PRAYER_TIMES[entity_id_name])
            state = hass.states.get(entity_id)
            assert state.state == pt_dt.isoformat()
            assert state.name == entity_id_name


async def test_islamic_prayer_times_multiple_sensors(hass):
    """Test Islamic prayer times sensor with multiple sensors setup."""
    multiple_sensors = ['fajr', 'sunrise', 'dhuhr', 'asr', 'maghrib', 'isha',
                        'midnight']

    with MockDependency('prayer_times_calculator') as mock_pt_calc:
        mock_pt_calc.PrayerTimesCalculator.return_value.fetch_prayer_times \
            .return_value = PRAYER_TIMES

        config = {
            'sensor': {
                'platform': 'islamic_prayer_times',
                'sensors': multiple_sensors
            }
        }

        assert await async_setup_component(hass, 'sensor', config) is True

        for sensor in multiple_sensors:
            entity_id = ENTITY_ID_FORMAT.format(sensor)
            entity_id_name = sensor.capitalize()
            pt_dt = get_prayer_time_as_dt(PRAYER_TIMES[entity_id_name])
            state = hass.states.get(entity_id)
            assert state.state == pt_dt.isoformat()
            assert state.name == entity_id_name


async def test_islamic_prayer_times_with_calculation_method(hass):
    """Test Islamic prayer times configuration with calculation method."""
    sensors = ['fajr', 'maghrib']

    with MockDependency('prayer_times_calculator') as mock_pt_calc:
        mock_pt_calc.PrayerTimesCalculator.return_value.fetch_prayer_times \
            .return_value = PRAYER_TIMES

        config = {
            'sensor': {
                'platform': 'islamic_prayer_times',
                'calculation_method': 'mwl',
                'sensors': sensors
            }
        }

        assert await async_setup_component(hass, 'sensor', config) is True

        for sensor in sensors:
            entity_id = ENTITY_ID_FORMAT.format(sensor)
            entity_id_name = sensor.capitalize()
            pt_dt = get_prayer_time_as_dt(PRAYER_TIMES[entity_id_name])
            state = hass.states.get(entity_id)
            assert state.state == pt_dt.isoformat()
            assert state.name == entity_id_name


async def test_islamic_prayer_times_data_get_prayer_times(hass):
    """Test Islamic prayer times data fetcher."""
    with MockDependency('prayer_times_calculator') as mock_pt_calc:
        mock_pt_calc.PrayerTimesCalculator.return_value.fetch_prayer_times \
            .return_value = PRAYER_TIMES

        pt_data = IslamicPrayerTimesData(latitude=LATITUDE,
                                         longitude=LONGITUDE,
                                         calc_method=CALC_METHOD)

        assert pt_data.get_new_prayer_times() == PRAYER_TIMES
        assert pt_data.prayer_times_info == PRAYER_TIMES


async def test_islamic_prayer_times_sensor_update(hass):
    """Test Islamic prayer times sensor update."""
    new_prayer_times = {"Fajr": "06:10",
                        "Sunrise": "07:25",
                        "Dhuhr": "12:30",
                        "Asr": "15:32",
                        "Maghrib": "17:45",
                        "Isha": "18:53",
                        "Midnight": "00:45"}

    with MockDependency('prayer_times_calculator') as mock_pt_calc:
        mock_pt_calc.PrayerTimesCalculator.return_value.fetch_prayer_times \
            .side_effect = [PRAYER_TIMES, new_prayer_times]

        config = {
            'sensor': {
                'platform': 'islamic_prayer_times',
                'sensors': ['maghrib']
            }
        }

        assert await async_setup_component(hass, 'sensor', config)

        entity_id = 'sensor.islamic_prayer_time_maghrib'
        pt_dt = get_prayer_time_as_dt(PRAYER_TIMES['Maghrib'])
        state = hass.states.get(entity_id)
        assert state.state == pt_dt.isoformat()

        midnight = PRAYER_TIMES['Midnight']
        now = dt_util.as_local(dt_util.now())
        today = now.date()

        midnight_dt_str = '{}::{}'.format(str(today), midnight)
        midnight_dt = datetime.strptime(midnight_dt_str, '%Y-%m-%d::%H:%M')
        future = midnight_dt + timedelta(days=1, minutes=1)

        with patch(
                'homeassistant.components.sensor.islamic_prayer_times'
                '.dt_util.utcnow', return_value=future):

            async_fire_time_changed(hass, future)
            await hass.async_block_till_done()
            state = hass.states.get(entity_id)
            pt_dt = get_prayer_time_as_dt(new_prayer_times['Maghrib'])
            assert state.state == pt_dt.isoformat()
