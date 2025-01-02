"""The tests for the folder_watcher component."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components import folder_watcher
from homeassistant.components.folder_watcher.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_invalid_path_setup(
    hass: HomeAssistant,
    tmp_path: Path,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that an invalid path is not set up."""
    freezer.move_to("2022-04-19 10:31:02+00:00")
    path = tmp_path.as_posix()
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        title=f"Folder Watcher {path!s}",
        data={},
        options={"folder": str(path), "patterns": ["*"]},
        entry_id="1",
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert len(issue_registry.issues) == 1


async def test_valid_path_setup(
    hass: HomeAssistant, tmp_path: Path, freezer: FrozenDateTimeFactory
) -> None:
    """Test that a valid path is setup."""
    freezer.move_to("2022-04-19 10:31:02+00:00")
    path = tmp_path.as_posix()
    hass.config.allowlist_external_dirs = {path}
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        title=f"Folder Watcher {path!s}",
        data={},
        options={"folder": str(path), "patterns": ["*"]},
        entry_id="1",
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


def test_event() -> None:
    """Check that Home Assistant events are fired correctly on watchdog event."""

    class MockPatternMatchingEventHandler:
        """Mock base class for the pattern matcher event handler."""

        def __init__(self, patterns) -> None:
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

        def __init__(self, patterns) -> None:
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
