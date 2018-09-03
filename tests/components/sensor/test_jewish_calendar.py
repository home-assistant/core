"""The tests for the Jewish calendar sensor platform."""
import unittest
from datetime import datetime as dt
# from unittest.mock import patch

from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.setup import setup_component
from homeassistant.components.sensor.jewish_calendar import JewishCalSensor
from tests.common import get_test_home_assistant


class TestJewishCalenderSensor(unittest.TestCase):
    """Test the Jewish Calendar sensor."""

    def setUp(self):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def checkForLoggingErrors(self):
        """Check whether logger spitted out errors."""
        errors = [rec for rec in self.cm.records if rec.levelname == "ERROR"]
        self.assertFalse(errors, ("Logger reported error(s): ",
                                  [err.getMessage() for err in errors]))

    def test_jewish_calendar_min_config(self):
        """Test minimum jewish calendar configuration."""
        config = {
            'sensor': {
                'platform': 'jewish_calendar',
                'date': '2018-09-03',
            }
        }
        with self.assertLogs() as self.cm:
            assert setup_component(self.hass, 'sensor', config)
        self.checkForLoggingErrors()

    # def test_uptime_sensor_name_change(self):
    #     """Test uptime sensor with different name."""
    #     config = {
    #         'sensor': {
    #             'platform': 'uptime',
    #             'name': 'foobar',
    #         }
    #     }
    #     assert setup_component(self.hass, 'sensor', config)

    # def test_uptime_sensor_config_hours(self):
    #     """Test uptime sensor with hours defined in config."""
    #     config = {
    #         'sensor': {
    #             'platform': 'uptime',
    #             'unit_of_measurement': 'hours',
    #         }
    #     }
    #     assert setup_component(self.hass, 'sensor', config)

    # def test_uptime_sensor_config_minutes(self):
    #     """Test uptime sensor with minutes defined in config."""
    #     config = {
    #         'sensor': {
    #             'platform': 'uptime',
    #             'unit_of_measurement': 'minutes',
    #         }
    #     }
    #     assert setup_component(self.hass, 'sensor', config)

    def test_jewish_calendar_sensor_date_output(self):
        """Test Jewish calendar sensor date output."""
        sensor = JewishCalSensor('test', dt(2018, 9, 3))
        run_coroutine_threadsafe(
            sensor.async_update(),
            self.hass.loop).result()
        self.assertEqual(sensor.state, 'Monday 23 Elul 5778')
    #     new_time = sensor.initial + timedelta(days=111.499)
    #     with patch('homeassistant.util.dt.now', return_value=new_time):
    #         run_coroutine_threadsafe(
    #             sensor.async_update(),
    #             self.hass.loop
    #         ).result()
    #         self.assertEqual(sensor.state, 111.50)

    # def test_uptime_sensor_hours_output(self):
    #     """Test uptime sensor output data."""
    #     sensor = UptimeSensor('test', 'hours')
    #     self.assertEqual(sensor.unit_of_measurement, 'hours')
    #     new_time = sensor.initial + timedelta(hours=16)
    #     with patch('homeassistant.util.dt.now', return_value=new_time):
    #         run_coroutine_threadsafe(
    #             sensor.async_update(),
    #             self.hass.loop
    #         ).result()
    #         self.assertEqual(sensor.state, 16.00)
    #     new_time = sensor.initial + timedelta(hours=72.499)
    #     with patch('homeassistant.util.dt.now', return_value=new_time):
    #         run_coroutine_threadsafe(
    #             sensor.async_update(),
    #             self.hass.loop
    #         ).result()
    #         self.assertEqual(sensor.state, 72.50)

    # def test_uptime_sensor_minutes_output(self):
    #     """Test uptime sensor output data."""
    #     sensor = UptimeSensor('test', 'minutes')
    #     self.assertEqual(sensor.unit_of_measurement, 'minutes')
    #     new_time = sensor.initial + timedelta(minutes=16)
    #     with patch('homeassistant.util.dt.now', return_value=new_time):
    #         run_coroutine_threadsafe(
    #             sensor.async_update(),
    #             self.hass.loop
    #         ).result()
    #         self.assertEqual(sensor.state, 16.00)
    #     new_time = sensor.initial + timedelta(minutes=12.499)
    #     with patch('homeassistant.util.dt.now', return_value=new_time):
    #         run_coroutine_threadsafe(
    #             sensor.async_update(),
    #             self.hass.loop
    #         ).result()
    #         self.assertEqual(sensor.state, 12.50)
