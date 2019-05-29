"""The tests for the myfitnesspal sensor."""
import unittest
from unittest.mock import patch

from tests.common import get_test_home_assistant

from homeassistant.const import STATE_UNKNOWN
from homeassistant.setup import setup_component

VALID_CONFIG = {
    "platform": "myfitnesspal",
    "username": "person@email.com",
    "password": "asdf45678thjk"
}


def get_empty_totals():
    """Mock TransportNSW departures loading."""
    data = {}
    return {'totals': data}


def get_filled_totals():
    """Mock TransportNSW departures loading."""
    data = {
        'calories': 123,
        'sodium': 234,
        'protein': 345,
        'sugar': 456,
        'carbohydrates': 567,
        'fat': 789
    }
    return {'totals': data}


class TestMyFitnessPal(unittest.TestCase):
    """Test the myfitnesspal sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test the mold indicator sensor setup."""
        assert setup_component(
                self.hass, 'sensor', {'sensor': self.config})

        mfp_sensor = self.hass.states.get('sensor.myfitnesspal_totals')
        assert mfp_sensor
        assert 'kcal' == mfp_sensor.attributes.get('unit_of_measurement')
        assert mfp_sensor.state == 'unknown'

    @patch('myfitnesspal.Client.get_date',
           side_effect=get_empty_totals)
    @patch('myfitnesspal.Client')
    def test_empty_day(self, mock_totals, mock_client):
        """Test invalid sensor values."""
        assert setup_component(
                self.hass, 'sensor', {'sensor': self.config})

        mfp_sensor = self.hass.states.get('sensor.myfitnesspal_totals')
        assert mfp_sensor
        assert 'kcal' == mfp_sensor.attributes.get('unit_of_measurement')
        assert mfp_sensor.state == 'unknown'

    @patch('myfitnesspal.Client.get_date',
           side_effect=get_filled_totals)
    @patch('myfitnesspal.Client')
    def test_pulling_data(self, mock_totals, mock_client):
        """Test invalid sensor values."""
        assert setup_component(
                self.hass, 'sensor', {'sensor': self.config})

        mfp_sensor = self.hass.states.get('sensor.myfitnesspal_totals')
        assert mfp_sensor
        assert 'kcal' == mfp_sensor.attributes.get('unit_of_measurement')
        assert mfp_sensor.state == 123
