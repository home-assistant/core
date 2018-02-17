"""The tests for the filesize sensor."""
import unittest
from unittest.mock import Mock, patch

from homeassistant.components.sensor.filesize import CONF_FILE_PATHS
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, mock_registry

PATH = '/Users/robincole/.homeassistant/home-assistant_v2.db'


class FakeObj():
    '''Fake object for testing.'''
    def __init__(self, stat, mtime, st_mode):
        self.st_size = stat
        self.st_mtime = mtime
        self.st_mode = st_mode


FAKE = FakeObj(37990000, 1518126363.5514238, 33188)


class TestFileSensor(unittest.TestCase):
    """Test the filesize sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_registry(self.hass)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('os.path.isfile', Mock(return_value=True))
    @patch('os.access', Mock(return_value=True))
    @patch('os.stat', Mock(return_value=FAKE))
    def test_filesize_class(self):

        config = {
            'sensor': {
                'platform': 'filesize',
                CONF_FILE_PATHS: [PATH]}
        }

        self.assertTrue(
            setup_component(self.hass, 'sensor', config))

        state = self.hass.states.get('sensor.homeassistant_v2db')

        assert state.state == 37.99
        assert state.attributes.get('bytes') == 37990000
        assert state.attributes.get(
            'last_updated') == '2018-02-08 21:46:03.551424'
        assert state.attributes.get('path') == PATH
