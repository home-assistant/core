"""The tests for the folder_watcher component."""
import unittest
from unittest.mock import patch, MagicMock  # , Mock
import os

import pytest

from homeassistant.components.folder_watcher import (
    DOMAIN, CONF_FOLDER, DEFAULT_PATTERN, create_event_handler)
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant

CWD = os.path.join(os.path.dirname(__file__))


def get_fake_event(src_path='test/file.txt', event_type='deleted'):
    """Generate a Fake watchdog event object with the specified arguments."""
    return MagicMock(src_path=src_path, event_type=event_type)


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
            DOMAIN: [{CONF_FOLDER: 'invalid_path'}]
        }
        self.assertFalse(
            setup_component(self.hass, DOMAIN, config))

    def test_valid_path_setup(self):
        """Test that a valid path is setup."""
        config = {
            DOMAIN: [{CONF_FOLDER: CWD}]
        }

        self.assertTrue(setup_component(self.hass, DOMAIN, config))

    def test_event(self):
        """Check that HASS events are fired correctly on watchdog event."""
        event_handler = create_event_handler([DEFAULT_PATTERN], self.hass)
        fake_event = get_fake_event()
        event_handler.process(fake_event)
