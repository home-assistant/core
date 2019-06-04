"""The tests for the myfitnesspal sensor."""
import unittest
from unittest.mock import patch

from tests.common import MockDependency, get_test_home_assistant

from homeassistant.components.myfitnesspal.sensor import MyFitnessPalSensor
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_UNKNOWN
from homeassistant.setup import setup_component

VALID_CONFIG = {'sensor': {
        "platform": "myfitnesspal",
        "username": "person@email.com",
        "password": "asdf45678thjk"
    }
}


class MockMFPClient():
    """Mock class for tmdbsimple library."""

    def __init__(self):
        """Add mock data for API return."""
        dfkdsfkdspfk()
        print('woooo')

    def get_date(self):
        """Return an instance of a sunbreddit."""
        print('hi')
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

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @MockDependency('myfitnesspal')
    @patch('myfitnesspal.Client', new=MockMFPClient)
    def test_setup(self, c):
        """Test the mold indicator sensor setup."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG)

        mfp_sensor = self.hass.states.get('sensor.myfitnesspal_totals')
        assert mfp_sensor
        assert 'kcal' == mfp_sensor.attributes.get('unit_of_measurement')
        assert mfp_sensor.state == 'unknown'

    @MockDependency('myfitnesspal')
    @patch('myfitnesspal.Client', new=MockMFPClient)
    def test_empty_day(self, c):
        """Test invalid sensor values."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG)

        mfp_sensor = self.hass.states.get('sensor.myfitnesspal_totals')
        assert mfp_sensor
        assert 'kcal' == mfp_sensor.attributes.get('unit_of_measurement')
        assert mfp_sensor.state == 0

    @MockDependency('myfitnesspal')
    @patch('myfitnesspal.Client', new=MockMFPClient)
    def test_pulling_data(self, c):
        """Test invalid sensor values."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG)

        mfp_sensor = self.hass.states.get('sensor.myfitnesspal_totals')
        assert mfp_sensor
        assert 'kcal' == mfp_sensor.attributes.get('unit_of_measurement')
        assert mfp_sensor.state == 124
