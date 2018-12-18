"""The tests for the Islamic prayer times sensor platform."""
from datetime import datetime
from homeassistant.setup import async_setup_component
from homeassistant.components.sensor.islamic_prayer_times import (
    IslamicPrayerTimesData, IslamicPrayerTimeSensor)
from tests.common import MockDependency
import homeassistant.util.dt as dt_util

LATITUDE = 41
LONGITUDE = -87
CALC_METHOD = 'isna'
PRAYER_TIMES = {"Fajr": "06:10", "Sunrise": "07:25", "Dhuhr": "12:30",
                "Asr": "15:32", "Maghrib": "17:35", "Isha": "18:53",
                "Midnight": "00:45"}


def get_prayer_time_as_dt(prayer_time):
    """Create a datetime object for the respective prayer time."""
    today = datetime.today().strftime('%Y-%m-%d')
    date_time_str = '{} {}'.format(str(today), prayer_time)
    pt_dt = dt_util.parse_datetime(date_time_str)
    return pt_dt


async def test_islamic_prayer_times_min_config(hass):
    """Test minimum Islamic prayer times configuration."""
    config = {
        'sensor': {
            'platform': 'islamic_prayer_times'
        }
    }
    assert await async_setup_component(hass, 'sensor', config) is True


async def test_islamic_prayer_times_multiple_sensors(hass):
    """Test Islamic prayer times sensor with multiple sensors setup."""
    config = {
        'sensor': {
            'platform': 'islamic_prayer_times',
            'sensors': [
                'fajr', 'sunrise', 'dhuhr', 'asr', 'maghrib', 'isha',
                'midnight'
            ]
        }
    }
    assert await async_setup_component(hass, 'sensor', config) is True


async def test_islamic_prayer_times_with_calculation_method(hass):
    """Test Islamic prayer times configuration with calculation method."""
    config = {
        'sensor': {
            'platform': 'islamic_prayer_times',
            'calculation_method': 'mwl'
        }
    }
    assert await async_setup_component(hass, 'sensor', config) is True


async def test_islamic_prayer_times_data_init():
    """Test Islamic prayer times data object creation."""
    pt_data = IslamicPrayerTimesData(latitude=LATITUDE,
                                     longitude=LONGITUDE,
                                     calc_method=CALC_METHOD)
    assert pt_data.latitude == LATITUDE
    assert pt_data.longitude == LONGITUDE
    assert pt_data.calc_method == CALC_METHOD
    assert pt_data.prayer_times is None


async def test_islamic_prayer_times_data_get_prayer_times(hass):
    """Test Islamic prayer times data fetcher."""
    with MockDependency('prayer_times_calculator') as mock_pt_calc:
        mock_pt_calc.PrayerTimesCalculator.return_value.fetch_prayer_times \
            .return_value = PRAYER_TIMES

        pt_data = IslamicPrayerTimesData(latitude=LATITUDE,
                                         longitude=LONGITUDE,
                                         calc_method=CALC_METHOD)

        assert pt_data.get_prayer_times() == PRAYER_TIMES
        assert pt_data.prayer_times == PRAYER_TIMES


async def test_islamic_prayer_times_sensor(hass):
    """Test Islamic prayer times sensor creation."""
    with MockDependency('prayer_times_calculator') as mock_pt_calc:
        mock_pt_calc.prayer_times = PRAYER_TIMES
        pt_sensor = IslamicPrayerTimeSensor('fajr', mock_pt_calc)
        assert pt_sensor.sensor_type == 'fajr'
        assert pt_sensor.entity_id == 'sensor.islamic_prayer_time_fajr'
        assert pt_sensor.prayer_times_data == mock_pt_calc


async def test_islamic_prayer_times_sensor_properties(hass):
    """Test Islamic prayer times sensor properties."""
    with MockDependency('prayer_times_calculator') as mock_pt_calc:
        mock_pt_calc.prayer_times = PRAYER_TIMES
        pt_sensor = IslamicPrayerTimeSensor('maghrib', mock_pt_calc)
        pt_dt = get_prayer_time_as_dt(mock_pt_calc.prayer_times['Maghrib'])
        assert pt_sensor.name == 'Maghrib'
        assert pt_sensor.icon == 'mdi:calendar-clock'
        assert pt_sensor.state == pt_dt.isoformat()
        assert pt_sensor.should_poll is False


async def test_islamic_prayer_times_sensor_update(hass):
    """Test Islamic prayer times sensor update."""
    with MockDependency('prayer_times_calculator') as mock_pt_calc:
        mock_pt_calc.prayer_times = PRAYER_TIMES
        pt_sensor = IslamicPrayerTimeSensor('maghrib', mock_pt_calc)
        pt_dt = get_prayer_time_as_dt(mock_pt_calc.prayer_times['Maghrib'])
        pt_sensor.hass = hass
        assert pt_sensor.state == pt_dt.isoformat()
        mock_pt_calc.prayer_times = {'Maghrib': '17:45'}
        await pt_sensor.async_update()
        pt_dt = get_prayer_time_as_dt(mock_pt_calc.prayer_times['Maghrib'])
        assert pt_sensor.state == pt_dt.isoformat()
