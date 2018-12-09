"""The tests for the Islamic prayer times sensor platform."""
from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant
from homeassistant.components.sensor.islamic_prayer_times import (
    IslamicPrayerTimesData, IslamicPrayerTimeSensor)
from tests.common import MockDependency

LATITUDE = 41
LONGITUDE = -87
CALC_METHOD = 'isna'
PRAYER_TIMES = {"Fajr": "06:10", "Sunrise": "07:25", "Dhuhr": "12:30",
                "Asr": "15:32", "Maghrib": "17:35", "Isha": "18:53",
                "Midnight": "00:45"}


class TestIslamicPrayerTimesSensor():
    """Test the Islamic Prayer Times sensor."""

    def setup_method(self, method):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_islamic_prayer_times_min_config(self):
        """Test minimum Islamic prayer times configuration."""
        config = {
            'sensor': {
                'platform': 'islamic_prayer_times'
            }
        }
        assert setup_component(self.hass, 'sensor', config)

    def test_islamic_prayer_times_multiple_sensors(self):
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
        assert setup_component(self.hass, 'sensor', config)

    def test_islamic_prayer_times_with_calculation_method(self):
        """Test Islamic prayer times configuration with calculation method."""
        config = {
            'sensor': {
                'platform': 'islamic_prayer_times',
                'calculation_method': 'mwl'
            }
        }
        assert setup_component(self.hass, 'sensor', config)

    def test_islamic_prayer_times_data_init(self):
        """Test Islamic prayer times data object creation."""
        pt_data = IslamicPrayerTimesData(latitude=LATITUDE,
                                         longitude=LONGITUDE,
                                         calc_method=CALC_METHOD)
        assert pt_data.latitude == LATITUDE
        assert pt_data.longitude == LONGITUDE
        assert pt_data.calc_method == CALC_METHOD
        assert pt_data.prayer_times is None

    @MockDependency('prayer_times_calculator')
    def test_islamic_prayer_times_data_get_prayer_times(self, mock_pt_calc):
        """Test Islamic prayer times data fetcher."""
        mock_pt_calc.PrayerTimesCalculator.return_value.fetch_prayer_times\
            .return_value = PRAYER_TIMES

        pt_data = IslamicPrayerTimesData(latitude=LATITUDE,
                                         longitude=LONGITUDE,
                                         calc_method=CALC_METHOD)

        assert pt_data.get_prayer_times() == PRAYER_TIMES
        assert pt_data.prayer_times == PRAYER_TIMES

    @MockDependency('prayer_times_calculator')
    def test_islamic_prayer_times_sensor(self, mock_pt_calc):
        """Test Islamic prayer times sensor creation."""
        mock_pt_calc.prayer_times = PRAYER_TIMES
        pt_sensor = IslamicPrayerTimeSensor('fajr', mock_pt_calc)
        assert pt_sensor.sensor_type == 'fajr'
        assert pt_sensor.entity_id == 'sensor.islamic_prayer_time_fajr'
        assert pt_sensor.prayer_times_data == mock_pt_calc

    @MockDependency('prayer_times_calculator')
    def test_islamic_prayer_times_sensor_properties(self, mock_pt_calc):
        """Test Islamic prayer times sensor properties."""
        mock_pt_calc.prayer_times = PRAYER_TIMES
        pt_sensor = IslamicPrayerTimeSensor('maghrib', mock_pt_calc)
        assert pt_sensor.name == 'Maghrib'
        assert pt_sensor.icon == 'mdi:calendar-clock'
        assert pt_sensor.state == '05:35PM'
        assert pt_sensor.should_poll is False

    @MockDependency('prayer_times_calculator')
    def test_islamic_prayer_times_sensor_update(self, mock_pt_calc):
        """Test Islamic prayer times sensor update."""
        mock_pt_calc.prayer_times = PRAYER_TIMES
        pt_sensor = IslamicPrayerTimeSensor('maghrib', mock_pt_calc)
        pt_sensor.hass = self.hass
        assert pt_sensor.state == '05:35PM'
        mock_pt_calc.prayer_times = {'Maghrib': '17:45'}
        run_coroutine_threadsafe(pt_sensor.async_update(),
                                 self.hass.loop).result()
        assert pt_sensor.state == '05:45PM'
