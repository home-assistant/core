"""The test for the version sensor platform."""
import asyncio
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

MOCK_VERSION = '10.0'


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
            }
        }

        assert setup_component(self.hass, 'sensor', config)

    @asyncio.coroutine
    def test_version(self):
        """Test the Version sensor."""
        config = {
            'sensor': {
                'platform': 'version',
                'name': 'test',
            }
        }

        with patch('homeassistant.const.__version__', MOCK_VERSION):
            assert setup_component(self.hass, 'sensor', config)
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.test')

        assert state.state == '10.0'
