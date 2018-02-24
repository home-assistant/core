"""The test for the data filter sensor platform."""
import unittest

from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, assert_setup_component


class TestDataFilterSensor(unittest.TestCase):
    """Test the Data Filter sensor."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.values = [20, 19, 18, 21, 22, 0]

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_fail(self):
        """Test if filter doesn't exist."""
        config = {
            'sensor': {
                'platform': 'data_filter',
                'entity_id': 'sensor.test_monitored',
                'filter': 'nonexisting'
            }
        }
        with assert_setup_component(0):
            assert setup_component(self.hass, 'sensor', config)

        self.hass.start()
        self.hass.block_till_done()

    def test_outlier(self):
        """Test if filter outlier works."""
        config = {
            'sensor': {
                'platform': 'data_filter',
                'name': 'test',
                'entity_id': 'sensor.test_monitored',
                'filter': 'outlier'
            }
        }
        with assert_setup_component(1):
            assert setup_component(self.hass, 'sensor', config)

        self.hass.start()
        self.hass.block_till_done()

        for value in self.values:
            self.hass.states.set(config['sensor']['entity_id'], value)
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.test')
        self.assertEqual('22.0', state.state)

    def test_lowpass(self):
        """Test if filter lowpass works."""
        config = {
            'sensor': {
                'platform': 'data_filter',
                'name': 'test',
                'entity_id': 'sensor.test_monitored',
                'filter': 'lowpass'
            }
        }
        with assert_setup_component(1):
            assert setup_component(self.hass, 'sensor', config)

        self.hass.start()
        self.hass.block_till_done()

        for value in self.values:
            self.hass.states.set(config['sensor']['entity_id'], value)
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.test')
        self.assertEqual(15.2, round(float(state.state), 1))
