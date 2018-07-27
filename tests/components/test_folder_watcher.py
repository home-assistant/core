"""The tests for the folder_watcher component."""
from unittest.mock import Mock, patch
import os

from homeassistant.components import folder_watcher
from homeassistant.setup import async_setup_component
from tests.common import MockDependency


async def test_invalid_path_setup(hass):
    """Test that an invalid path is not setup."""
    assert not await async_setup_component(
        hass, folder_watcher.DOMAIN, {
            folder_watcher.DOMAIN: {
                    folder_watcher.CONF_FOLDER: 'invalid_path'
            }
        })


async def test_valid_path_setup(hass):
    """Test that a valid path is setup."""
    cwd = os.path.join(os.path.dirname(__file__))
    hass.config.whitelist_external_dirs = set((cwd))
    with patch.object(folder_watcher, 'Watcher'):
        assert await async_setup_component(
            hass, folder_watcher.DOMAIN, {
                folder_watcher.DOMAIN: {folder_watcher.CONF_FOLDER: cwd}
            })


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
