"""The tests for the filesize sensor."""
import unittest
import os
from unittest.mock import Mock, patch

from homeassistant.components.sensor.filesize import CONF_FILE_PATHS
from homeassistant.setup import setup_component
import homeassistant.core as ha
from tests.common import get_test_home_assistant, mock_registry


TEST_DIR = os.path.join(os.path.dirname(__file__))
TEST_FILE = os.path.join(TEST_DIR, 'mock_file_test_filesize.txt')

def create_file(path):
    """Create a test file."""
    with open(path, 'w') as test_file:
        test_file.write("test")

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
        self.hass.config.whitelist_external_dirs = set((TEST_DIR))
        mock_registry(self.hass)

    def teardown_method(self, method):
        """Stop everything that was started."""
        if os.path.isfile(TEST_FILE):
            os.remove(TEST_FILE)
        
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

    def test_valid_path(self):
        """Test for a valid path."""
        create_file(TEST_FILE)

        config = {
            'sensor': {
                'platform': 'filesize',
                CONF_FILE_PATHS: [TEST_FILE]}
        }

        self.assertTrue(
            setup_component(self.hass, 'sensor', config))

        assert len(self.hass.states.entity_ids()) == 1


"""
        #state = self.hass.states.get('sensor.test_api_streamspy')

    #    assert state.state == 37.99
    #    assert state.attributes.get('bytes') == 37990000
    #    assert state.attributes.get(
    #        'last_updated') == '2018-02-08 21:46:03.551424'
    #    assert state.attributes.get('path') == PATH
"""
