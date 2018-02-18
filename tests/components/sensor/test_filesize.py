"""The tests for the filesize sensor."""
import unittest
from unittest.mock import Mock, patch

from homeassistant.components.sensor.filesize import CONF_FILE_PATHS
from homeassistant.setup import setup_component
import homeassistant.core as ha
from tests.common import get_test_home_assistant, mock_registry


class FakeObj():
    '''Fake object for testing.'''
    def __init__(self, stat, mtime, st_mode):
        self.st_size = stat
        self.st_mtime = mtime
        self.st_mode = st_mode


class TestFileSensor(unittest.TestCase):
    """Test the filesize sensor."""

    FAKE = FakeObj(37990000, 1518126363.5514238, 33188)

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.config = ha.Config()
        mock_registry(self.hass)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_invalid_path(self):
        """Test that an invalid path is caught."""
        config = {
            'sensor': {
                'platform': 'filesize',
                CONF_FILE_PATHS: ['mock.file1']}
        }

        self.assertTrue(
            setup_component(self.hass, 'sensor', config))

        assert len(self.hass.states.entity_ids()) == 0

    @patch('os.stat', Mock(return_value=FAKE))
    def test_valid_path(self):
        """Test for a valid path."""
        config = {
            'sensor': {
                'platform': 'filesize',
                CONF_FILE_PATHS: ['/tests/components/sensor/test_filesize.py']}
        }

        self.config.whitelist_external_dirs = set(('/tests/components/sensor/'))
        self.assertTrue(
            setup_component(self.hass, 'sensor', config))

        assert len(self.hass.states.entity_ids()) == 1

        #state = self.hass.states.get('sensor.test_api_streamspy')

    #    assert state.state == 37.99
    #    assert state.attributes.get('bytes') == 37990000
    #    assert state.attributes.get(
    #        'last_updated') == '2018-02-08 21:46:03.551424'
    #    assert state.attributes.get('path') == PATH
