"""The test for the version sensor platform."""
import unittest

from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

MOCK_VERSION = '10.0'
MOCK_DEV_VERSION = '10.0.dev0'


class TestVersionSensor(unittest.TestCase):
    """Test the Version sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_version_sensor(self):
        """Test the Version sensor."""
        config = {
            'sensor': {
                'platform': 'version',
                'name': 'test',
            }
        }

        assert setup_component(self.hass, 'sensor', config)

        self.hass.states.set('sensor.test', MOCK_VERSION)
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test')

        self.assertEqual(state.state, '10.0')

    def test_version_sensor_dev(self):
        """Test the Version sensor."""
        config = {
            'sensor': {
                'platform': 'version',
                'name': 'test_dev',
            }
        }

        assert setup_component(self.hass, 'sensor', config)

        self.hass.states.set('sensor.test_dev', MOCK_DEV_VERSION)
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_dev')

        self.assertEqual(state.state, '10.0.dev0')
