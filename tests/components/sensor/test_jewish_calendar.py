"""The tests for the Jewish calendar sensor platform."""
import unittest
from datetime import time
from datetime import datetime as dt
from unittest.mock import patch

from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.setup import setup_component
from homeassistant.components.sensor.jewish_calendar import JewishCalSensor
from tests.common import get_test_home_assistant


class TestJewishCalenderSensor(unittest.TestCase):
    """Test the Jewish Calendar sensor."""

    TEST_LATITUDE = 31.778
    TEST_LONGITUDE = 35.235

    def setUp(self):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_jewish_calendar_min_config(self):
        """Test minimum jewish calendar configuration."""
        config = {
            'sensor': {
                'platform': 'jewish_calendar'
            }
        }
        assert setup_component(self.hass, 'sensor', config)

    def test_jewish_calendar_hebrew(self):
        """Test jewish calendar sensor with language set to hebrew."""
        config = {
            'sensor': {
                'platform': 'jewish_calendar',
                'language': 'hebrew',
            }
        }

        assert setup_component(self.hass, 'sensor', config)

    def test_jewish_calendar_multiple_sensors(self):
        """Test jewish calendar sensor with multiple sensors setup."""
        config = {
            'sensor': {
                'platform': 'jewish_calendar',
                'sensors': [
                    'date', 'weekly_portion', 'holiday_name',
                    'holyness', 'first_light', 'gra_end_shma',
                    'mga_end_shma', 'plag_mincha', 'first_stars'
                ]
            }
        }

        assert setup_component(self.hass, 'sensor', config)

    def test_jewish_calendar_sensor_date_output(self):
        """Test Jewish calendar sensor date output."""
        test_time = dt(2018, 9, 3)
        sensor = JewishCalSensor(
            name='test', language='english', sensor_type='date',
            latitude=self.TEST_LATITUDE, longitude=self.TEST_LONGITUDE,
            timezone="UTC", diaspora=False)
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(),
                self.hass.loop).result()
            self.assertEqual(sensor.state, '23 Elul 5778')

    def test_jewish_calendar_sensor_date_output_hebrew(self):
        """Test Jewish calendar sensor date output in hebrew."""
        test_time = dt(2018, 9, 3)
        sensor = JewishCalSensor(
            name='test', language='hebrew', sensor_type='date',
            latitude=self.TEST_LATITUDE, longitude=self.TEST_LONGITUDE,
            timezone="UTC", diaspora=False)
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(), self.hass.loop).result()
            self.assertEqual(sensor.state, "כ\"ג באלול ה\' תשע\"ח")

    def test_jewish_calendar_sensor_holiday_name(self):
        """Test Jewish calendar sensor date output in hebrew."""
        test_time = dt(2018, 9, 10)
        sensor = JewishCalSensor(
            name='test', language='hebrew', sensor_type='holiday_name',
            latitude=self.TEST_LATITUDE, longitude=self.TEST_LONGITUDE,
            timezone="UTC", diaspora=False)
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(), self.hass.loop).result()
            self.assertEqual(sensor.state, "א\' ראש השנה")

    def test_jewish_calendar_sensor_holiday_name_english(self):
        """Test Jewish calendar sensor date output in hebrew."""
        test_time = dt(2018, 9, 10)
        sensor = JewishCalSensor(
            name='test', language='english', sensor_type='holiday_name',
            latitude=self.TEST_LATITUDE, longitude=self.TEST_LONGITUDE,
            timezone="UTC", diaspora=False)
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(), self.hass.loop).result()
            self.assertEqual(sensor.state, "Rosh Hashana I")

    def test_jewish_calendar_sensor_holyness(self):
        """Test Jewish calendar sensor date output in hebrew."""
        test_time = dt(2018, 9, 10)
        sensor = JewishCalSensor(
            name='test', language='hebrew', sensor_type='holyness',
            latitude=self.TEST_LATITUDE, longitude=self.TEST_LONGITUDE,
            timezone="UTC", diaspora=False)
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(), self.hass.loop).result()
            self.assertEqual(sensor.state, 1)

    def test_jewish_calendar_sensor_torah_reading(self):
        """Test Jewish calendar sensor date output in hebrew."""
        test_time = dt(2018, 9, 8)
        sensor = JewishCalSensor(
            name='test', language='hebrew', sensor_type='weekly_portion',
            latitude=self.TEST_LATITUDE, longitude=self.TEST_LONGITUDE,
            timezone="UTC", diaspora=False)
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(), self.hass.loop).result()
            self.assertEqual(sensor.state, "פרשת נצבים")

    def test_jewish_calendar_sensor_first_stars_ny(self):
        """Test Jewish calendar sensor date output in hebrew."""
        test_time = dt(2018, 9, 8)
        sensor = JewishCalSensor(
            name='test', language='hebrew', sensor_type='first_stars',
            latitude=40.7128, longitude=-74.0060,
            timezone="America/New_York", diaspora=False)
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(), self.hass.loop).result()
            self.assertEqual(sensor.state, time(19, 48))

    def test_jewish_calendar_sensor_first_stars_jerusalem(self):
        """Test Jewish calendar sensor date output in hebrew."""
        test_time = dt(2018, 9, 8)
        sensor = JewishCalSensor(
            name='test', language='hebrew', sensor_type='first_stars',
            latitude=self.TEST_LATITUDE, longitude=self.TEST_LONGITUDE,
            timezone="Asia/Jerusalem", diaspora=False)
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(), self.hass.loop).result()
            self.assertEqual(sensor.state, time(19, 21))
