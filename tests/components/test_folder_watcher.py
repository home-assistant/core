"""The tests for the folder_watcher component."""
import unittest
from unittest.mock import Mock
import os

from homeassistant.components import folder_watcher
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, MockDependency

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


@MockDependency('watchdog', 'events')
def test_event(mock_watchdog):
    """Check that HASS events are fired correctly on watchdog event."""
    class MockPatternMatchingEventHandler:
        """Mock base class for the pattern matcher event handler."""

        def __init__(self, patterns):
            pass

    mock_watchdog.events.PatternMatchingEventHandler = \
        MockPatternMatchingEventHandler
    hass = Mock()
    handler = folder_watcher.create_event_handler(['*'], hass)
    handler.on_created(Mock(
        is_directory=False,
        src_path='/hello/world.txt',
        event_type='created'
    ))
    assert hass.bus.fire.called
    assert hass.bus.fire.mock_calls[0][1][0] == folder_watcher.DOMAIN
    assert hass.bus.fire.mock_calls[0][1][1] == {
        'event_type': 'created',
        'path': '/hello/world.txt',
        'file': 'world.txt',
        'folder': '/hello',
    }
