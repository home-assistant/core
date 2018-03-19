"""The tests for the folder_watcher component."""
import unittest
import os

from homeassistant.components.folder_watcher import (
    DOMAIN, CONF_FOLDER)
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant

CWD = os.path.join(os.path.dirname(__file__))


class TestFolderWatcher(unittest.TestCase):
    """Test the file_watcher component."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.whitelist_external_dirs = set((CWD))

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_invalid_path_setup(self):
        """Test that a invalid path is not setup."""
        config = {
            DOMAIN: [{CONF_FOLDER: 'invalid_path'}]
        }
        self.assertFalse(
            setup_component(self.hass, DOMAIN, config))

    def test_valid_path_setup(self):
        """Test that a valid path is setup."""
        config = {
            DOMAIN: [{CONF_FOLDER: CWD}]
        }
        self.assertTrue(
            setup_component(self.hass, DOMAIN, config))
