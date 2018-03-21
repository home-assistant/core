"""The tests for the folder_watcher component."""
import unittest
from unittest.mock import patch, MagicMock
import os

import pytest

from homeassistant.components import folder_watcher
from homeassistant.core import callback
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant

CWD = os.path.join(os.path.dirname(__file__))
EVENT_TYPE = 'deleted'
SRC_PATH = 'test/file.txt'
FILE = 'file.txt'
FOLDER = 'test'


def get_fake_event(src_path=SRC_PATH, event_type=EVENT_TYPE):
    """Generate a Fake watchdog event object with the specified arguments."""
    return MagicMock(
        src_path=src_path, event_type=event_type, is_directory=False)


@pytest.fixture(autouse=True)
def watchdog_mock():
    """Mock watchdog module."""
    with patch.dict('sys.modules', {
        'watchdog': MagicMock(),
        'watchdog.observers': MagicMock(),
        'watchdog.events': MagicMock(),
    }):
        yield


class TestFolderWatcher(unittest.TestCase):
    """Test the file_watcher component."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.whitelist_external_dirs = set((CWD))
        self.events = []

        @callback
        def record_event(event):
            """Record HASS event."""
            self.events.append(event)

        self.hass.bus.listen(folder_watcher.DOMAIN, record_event)

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
        event_handler = folder_watcher.create_event_handler(
            [folder_watcher.DEFAULT_PATTERN], self.hass)
        fake_event = get_fake_event()
        event_handler.process(fake_event)

        self.hass.block_till_done()
        last_event = self.events[-1]
        self.assertEqual(last_event.data["event_type"], EVENT_TYPE)
        self.assertEqual(last_event.data['path'], SRC_PATH)
        self.assertEqual(last_event.data['file'], FILE)
        self.assertEqual(last_event.data['folder'], FOLDER)
