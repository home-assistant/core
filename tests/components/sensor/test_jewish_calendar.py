"""The tests for the Jewish calendar sensor platform."""
import unittest
from datetime import datetime as dt
from unittest.mock import patch

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
                'platform': 'jewish_calendar'
            }
        }
        with self.assertLogs() as self.cm:
            assert setup_component(self.hass, 'sensor', config)
        self.checkForLoggingErrors()

    def test_jewish_calendar_hebrew(self):
        """Test jewish calendar sensor with language set to hebrew."""
        config = {
            'sensor': {
                'platform': 'jewish_calendar',
                'language': 'hebrew',
            }
        }
        with self.assertLogs() as self.cm:
            assert setup_component(self.hass, 'sensor', config)
        self.checkForLoggingErrors()

    def test_jewish_calendar_sensor_date_output(self):
        """Test Jewish calendar sensor date output."""
        test_time = dt(2018, 9, 3)
        sensor = JewishCalSensor('english')
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(),
                self.hass.loop).result()
            self.assertEqual(sensor.state, 'Monday 23 Elul 5778')

    def test_jewish_calendar_sensor_date_output_hebrew(self):
        """Test Jewish calendar sensor date output in hebrew."""
        test_time = dt(2018, 9, 3)
        sensor = JewishCalSensor('hebrew')
        with patch('homeassistant.util.dt.now', return_value=test_time):
            run_coroutine_threadsafe(
                sensor.async_update(),
                self.hass.loop).result()
            self.assertEqual(sensor.state, "יום שני כ\"ג באלול ה\' תשע\"ח")
