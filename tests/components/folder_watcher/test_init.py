"""The tests for the folder_watcher component."""
import os

from homeassistant.components import folder_watcher
from homeassistant.setup import async_setup_component

from tests.async_mock import Mock, patch


async def test_invalid_path_setup(hass):
    """Test that an invalid path is not set up."""
    assert not await async_setup_component(
        hass,
        folder_watcher.DOMAIN,
        {folder_watcher.DOMAIN: {folder_watcher.CONF_FOLDER: "invalid_path"}},
    )


async def test_valid_path_setup(hass):
    """Test that a valid path is setup."""
    cwd = os.path.join(os.path.dirname(__file__))
    hass.config.allowlist_external_dirs = {cwd}
    with patch.object(folder_watcher, "Watcher"):
        assert await async_setup_component(
            hass,
            folder_watcher.DOMAIN,
            {folder_watcher.DOMAIN: {folder_watcher.CONF_FOLDER: cwd}},
        )


def test_event():
    """Check that Home Assistant events are fired correctly on watchdog event."""

    class MockPatternMatchingEventHandler:
        """Mock base class for the pattern matcher event handler."""

        def __init__(self, patterns):
            pass

    with patch(
        "homeassistant.components.folder_watcher.PatternMatchingEventHandler",
        MockPatternMatchingEventHandler,
    ):
        hass = Mock()
        handler = folder_watcher.create_event_handler(["*"], hass)
        handler.on_created(
            Mock(is_directory=False, src_path="/hello/world.txt", event_type="created")
        )
        assert hass.bus.fire.called
        assert hass.bus.fire.mock_calls[0][1][0] == folder_watcher.DOMAIN
        assert hass.bus.fire.mock_calls[0][1][1] == {
            "event_type": "created",
            "path": "/hello/world.txt",
            "file": "world.txt",
            "folder": "/hello",
        }
