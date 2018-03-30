"""The tests for the folder_watcher component."""
import unittest
from unittest.mock import MagicMock
import os

from homeassistant.components import folder_watcher
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant

CWD = os.path.join(os.path.dirname(__file__))
FILE = 'file.txt'


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
            folder_watcher.DOMAIN: [{
                folder_watcher.CONF_FOLDER: 'invalid_path'
                }]
        }
        self.assertFalse(
            setup_component(self.hass, folder_watcher.DOMAIN, config))

    def test_valid_path_setup(self):
        """Test that a valid path is setup."""
        config = {
            folder_watcher.DOMAIN: [{folder_watcher.CONF_FOLDER: CWD}]
        }

        self.assertTrue(setup_component(
            self.hass, folder_watcher.DOMAIN, config))

    def test_event(self):
        """Check that HASS events are fired correctly on watchdog event."""
        from watchdog.events import FileModifiedEvent

        # Cant use setup_component as need to retrieve Watcher object.
        w = folder_watcher.Watcher(CWD,
                                   folder_watcher.DEFAULT_PATTERN,
                                   self.hass)
        w.startup(None)

        self.hass.bus.fire = MagicMock()

        # Trigger a fake filesystem event through the Watcher Observer emitter.
        (emitter,) = w._observer.emitters
        emitter.queue_event(FileModifiedEvent(FILE))

        # Wait for the event to propagate.
        self.hass.block_till_done()

        assert self.hass.bus.fire.called
