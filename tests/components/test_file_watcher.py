"""The tests for the folder_watcher component."""
import unittest
from unittest.mock import patch, MagicMock, Mock
import os

import pytest

from homeassistant.components import folder_watcher
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant

CWD = os.path.join(os.path.dirname(__file__))
EVENT_TYPE = 'deleted'
FILE = 'file.txt'
FOLDER = 'test'
SRC_PATH = 'test/file.txt'


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
        fake_hass = Mock()
        event_handler = folder_watcher.create_event_handler(
            [folder_watcher.DEFAULT_PATTERN], fake_hass)
        assert hasattr(event_handler, 'hass')
        assert hasattr(event_handler, 'process')

        fake_event = get_fake_event()
        assert not fake_event.is_directory
        event_handler.process(fake_event)  # Should call fake_hass.bus.fire
        event_handler.process.assert_called()

        expected_payload = {"event_type": fake_event.event_type,
                            'path': fake_event.src_path,
                            'file': FILE,
                            'folder': FOLDER}

        fake_hass.bus.fire.assert_called()
#        fake_hass.bus.fire.assert_called_with(
#            folder_watcher.DOMAIN, expected_payload)
