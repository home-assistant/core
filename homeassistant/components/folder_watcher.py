"""The tests for the folder_watcher component."""
import unittest
import os

from homeassistant.components.folder_watcher import (
    DOMAIN, CONF_FOLDER)
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant


CWD = os.path.join(os.path.dirname(__file__))
TEST_FOLDER = 'test_folder'
TEST_DIR = os.path.join(CWD, TEST_FOLDER)
TEST_TXT = 'mock_test_folder.txt'
TEST_FILE = os.path.join(TEST_DIR, TEST_TXT)


def create_file(path):
    """Create a test file."""
    with open(path, 'w') as test_file:
        test_file.write("test")


class TestFolderWatcher(unittest.TestCase):
    """Test the file_watcher component."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        if not os.path.isdir(TEST_DIR):
            os.mkdir(TEST_DIR)
        self.hass.config.whitelist_external_dirs = set((TEST_DIR))

    def teardown_method(self, method):
        """Stop everything that was started."""
        if os.path.isfile(TEST_FILE):
            os.remove(TEST_FILE)
            os.rmdir(TEST_DIR)
        self.hass.stop()

    def test_path(self):
        """Test that a valid path is setup."""
        config = {
            DOMAIN: [{CONF_FOLDER: TEST_DIR}]}
        self.assertTrue(
            setup_component(self.hass, DOMAIN, config))

    def test_invalid_path(self):
        """Test that a valid path is setup."""
        config = {
            DOMAIN: [{CONF_FOLDER: 'invalid_path'}]}
        self.assertFalse(
            setup_component(self.hass, DOMAIN, config))
