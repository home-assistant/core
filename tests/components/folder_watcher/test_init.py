"""The tests for the folder_watcher component."""

import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

from homeassistant.components import folder_watcher
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_invalid_path_setup(hass: HomeAssistant) -> None:
    """Test that an invalid path is not set up."""
    assert not await async_setup_component(
        hass,
        folder_watcher.DOMAIN,
        {folder_watcher.DOMAIN: {folder_watcher.CONF_FOLDER: "invalid_path"}},
    )


async def test_valid_path_setup(hass: HomeAssistant) -> None:
    """Test that a valid path is setup."""
    cwd = os.path.join(os.path.dirname(__file__))
    hass.config.allowlist_external_dirs = {cwd}
    with patch.object(folder_watcher, "Watcher"):
        assert await async_setup_component(
            hass,
            folder_watcher.DOMAIN,
            {folder_watcher.DOMAIN: {folder_watcher.CONF_FOLDER: cwd}},
        )


def test_event() -> None:
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
        handler = folder_watcher.create_event_handler(["*"], hass, "1")
        handler.on_created(
            SimpleNamespace(
                is_directory=False, src_path="/hello/world.txt", event_type="created"
            )
        )
        assert hass.bus.fire.called
        assert hass.bus.fire.mock_calls[0][1][0] == folder_watcher.DOMAIN
        assert hass.bus.fire.mock_calls[0][1][1] == {
            "event_type": "created",
            "path": "/hello/world.txt",
            "file": "world.txt",
            "folder": "/hello",
        }


def test_move_event() -> None:
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
        handler = folder_watcher.create_event_handler(["*"], hass, "1")
        handler.on_moved(
            SimpleNamespace(
                is_directory=False,
                src_path="/hello/world.txt",
                dest_path="/hello/earth.txt",
                event_type="moved",
            )
        )
        assert hass.bus.fire.called
        assert hass.bus.fire.mock_calls[0][1][0] == folder_watcher.DOMAIN
        assert hass.bus.fire.mock_calls[0][1][1] == {
            "event_type": "moved",
            "path": "/hello/world.txt",
            "dest_path": "/hello/earth.txt",
            "file": "world.txt",
            "dest_file": "earth.txt",
            "folder": "/hello",
            "dest_folder": "/hello",
        }
