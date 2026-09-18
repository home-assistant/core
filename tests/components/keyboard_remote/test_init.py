"""Tests for the Keyboard Remote integration init."""

import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

from asyncinotify import Mask

from homeassistant.components.keyboard_remote import (
    KeyboardRemoteManager,
    _async_import_yaml_device,
)
from homeassistant.components.keyboard_remote.const import (
    CONF_DEVICE_DESCRIPTOR,
    CONF_DEVICE_NAME,
    CONF_DEVICE_PATH,
    CONF_EMULATE_KEY_HOLD,
    CONF_EMULATE_KEY_HOLD_DELAY,
    CONF_EMULATE_KEY_HOLD_REPEAT,
    CONF_KEY_TYPES,
    DEFAULT_EMULATE_KEY_HOLD,
    DEFAULT_EMULATE_KEY_HOLD_DELAY,
    DEFAULT_EMULATE_KEY_HOLD_REPEAT,
    DOMAIN,
    EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED,
    EVENT_KEYBOARD_REMOTE_CONNECTED,
    EVENT_KEYBOARD_REMOTE_DISCONNECTED,
    KEY_CODE,
    KEY_VALUE,
    MATCH_DEVICE_PATH,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import (
    EV_KEY,
    FAKE_BY_ID_BASENAME,
    FAKE_DEVICE_NAME,
    FAKE_DEVICE_PATH,
    FAKE_DEVICE_REAL_PATH,
    MockAsyncIterator,
    make_key_event,
)

from tests.common import MockConfigEntry, async_capture_events

# --- Setup / unload tests ---


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_multiple_entries_shared_manager(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test multiple entries load and unload independently."""
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        unique_id="usb-Other_Device-event-kbd",
        title="Other Device",
        data={
            "device_path": "/dev/input/by-id/usb-Other_Device-event-kbd",
            "device_name": "Other Device",
        },
        options=mock_config_entry.options.copy(),
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert entry2.state is ConfigEntryState.LOADED

    # Unload first entry — second should still be loaded
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert entry2.state is ConfigEntryState.LOADED

    # Unload second entry
    await hass.config_entries.async_unload(entry2.entry_id)
    await hass.async_block_till_done()

    assert entry2.state is ConfigEntryState.NOT_LOADED


# --- YAML import tests ---


async def test_yaml_import_triggers_config_flow(hass: HomeAssistant) -> None:
    """Test that YAML config triggers import flow and creates deprecation issue."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        assert await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_descriptor": "/dev/input/event5"},
        )

    # Verify config entry was created
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data["device_path"] == FAKE_DEVICE_PATH


async def test_yaml_import_creates_deprecation_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import creates a deprecation repair issue."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        await _async_import_yaml_device(
            hass, {"device_descriptor": "/dev/input/event5"}
        )

    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN,
        issue_id=f"deprecated_yaml_{DOMAIN}",
    )


async def test_yaml_import_failure_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import failure creates an error issue."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(None, None, None),
    ):
        await _async_import_yaml_device(hass, {})

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id="deprecated_yaml_import_issue_cannot_identify_device",
    )


async def test_async_setup_no_yaml_config(hass: HomeAssistant) -> None:
    """Test setup succeeds when DOMAIN not in config."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def test_async_setup_with_yaml_config(hass: HomeAssistant) -> None:
    """Test setup creates import tasks for YAML device blocks."""
    with patch(
        "homeassistant.components.keyboard_remote._async_import_yaml_device",
        new_callable=AsyncMock,
    ) as mock_import:
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: [
                    {"device_descriptor": "/dev/input/event5"},
                    {"device_name": "Test Keyboard"},
                ]
            },
        )
        await hass.async_block_till_done()

    assert mock_import.call_count == 2


# --- DeviceHandler.matches_device tests ---


async def test_matches_device_by_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test matches_device returns True when configured path resolves to same real path."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]

    with (
        patch("os.path.realpath", return_value=FAKE_DEVICE_REAL_PATH),
        patch("os.path.exists", return_value=True),
    ):
        assert handler.matches_device(FAKE_DEVICE_REAL_PATH, mock_input_device) is True


async def test_matches_device_by_yaml_descriptor(
    hass: HomeAssistant,
    mock_input_device: MagicMock,
) -> None:
    """Test matches_device returns True when YAML descriptor resolves to same path."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_BY_ID_BASENAME,
        data={
            CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
            CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
            CONF_DEVICE_DESCRIPTOR: "/dev/input/event5",
        },
        options={
            CONF_KEY_TYPES: ["key_up"],
            CONF_EMULATE_KEY_HOLD: DEFAULT_EMULATE_KEY_HOLD,
            CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
            CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[entry.entry_id]

    with (
        patch("os.path.realpath", return_value=FAKE_DEVICE_REAL_PATH),
        patch("os.path.exists", return_value=False),
    ):
        assert handler.matches_device(FAKE_DEVICE_REAL_PATH, mock_input_device) is True


async def test_matches_device_by_name(
    hass: HomeAssistant,
    mock_input_device: MagicMock,
) -> None:
    """Test matches_device returns True when a name-only entry's name matches."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_DEVICE_NAME,
        data={CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
        options={
            CONF_KEY_TYPES: ["key_up"],
            CONF_EMULATE_KEY_HOLD: DEFAULT_EMULATE_KEY_HOLD,
            CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
            CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[entry.entry_id]

    with (
        patch("os.path.realpath", side_effect=lambda p: p),
        patch("os.path.exists", return_value=False),
    ):
        assert handler.matches_device("/dev/input/event99", mock_input_device) is True


async def test_no_name_match_when_entry_has_a_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test an entry with a configured path does not fall back to the name.

    The configured node being absent must leave the entry disconnected rather
    than binding a sibling node of a composite keyboard reporting the same name.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]

    with (
        patch("os.path.realpath", side_effect=lambda p: p),
        patch("os.path.exists", return_value=False),
    ):
        assert handler.matches_device("/dev/input/event99", mock_input_device) is False


async def test_matches_device_no_match(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test matches_device returns False when no strategy matches."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]
    dev = MagicMock()
    dev.name = "Unknown Device"

    with (
        patch("os.path.realpath", side_effect=lambda p: p),
        patch("os.path.exists", return_value=False),
    ):
        assert handler.matches_device("/dev/input/event99", dev) is False


async def test_scan_prefers_device_path_over_name_match(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a handler binds its configured device_path, not a same-named sibling.

    A composite keyboard exposes several nodes reporting one name, and only the
    node the user selected carries the by-id symlink. list_devices() returns
    them in arbitrary order, so the weaker name match must not win by arriving
    first.
    """
    sibling_path = "/dev/input/event9"
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    manager: KeyboardRemoteManager = hass.data[DOMAIN]

    devices = {}
    for path in (sibling_path, FAKE_DEVICE_REAL_PATH):
        dev = MagicMock()
        dev.name = FAKE_DEVICE_NAME
        dev.path = path
        dev.fileno.return_value = int(path.removeprefix("/dev/input/event"))
        dev.async_read_loop = MagicMock(return_value=MockAsyncIterator())
        devices[path] = dev

    def _realpath(path: str) -> str:
        return FAKE_DEVICE_REAL_PATH if path == FAKE_DEVICE_PATH else path

    with (
        # The by-id node is listed last, so a first-match scan picks the sibling
        patch("evdev.list_devices", return_value=[sibling_path, FAKE_DEVICE_REAL_PATH]),
        patch("evdev.InputDevice", side_effect=lambda path: devices[path]),
        patch("os.path.realpath", side_effect=_realpath),
        patch("os.path.exists", return_value=True),
    ):
        await manager._async_scan_initial_devices()
        await hass.async_block_till_done()

    assert list(manager._active_handlers_by_descriptor) == [FAKE_DEVICE_REAL_PATH]
    devices[sibling_path].close.assert_called_once()
    devices[FAKE_DEVICE_REAL_PATH].close.assert_not_called()


# --- DeviceHandler start/stop monitoring tests ---


async def test_device_start_monitoring_fires_connected_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test start monitoring fires the connected event with correct data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)

    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[CONF_DEVICE_DESCRIPTOR] == FAKE_DEVICE_PATH
    assert events[0].data[CONF_DEVICE_NAME] == FAKE_DEVICE_NAME
    assert handler.dev is mock_input_device


async def test_events_keep_the_imported_yaml_descriptor(
    hass: HomeAssistant,
    mock_input_device: MagicMock,
) -> None:
    """Test an imported YAML entry reports the descriptor it was configured with.

    Automations written against the pre-migration path must keep matching, even
    though the import also resolved a stable by-id path for the same device.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_BY_ID_BASENAME,
        data={
            CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
            CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
            CONF_DEVICE_DESCRIPTOR: FAKE_DEVICE_REAL_PATH,
        },
        options={
            CONF_KEY_TYPES: ["key_up"],
            CONF_EMULATE_KEY_HOLD: DEFAULT_EMULATE_KEY_HOLD,
            CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
            CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[entry.entry_id]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)

    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[CONF_DEVICE_DESCRIPTOR] == FAKE_DEVICE_REAL_PATH


async def test_device_start_monitoring_idempotent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test calling start monitoring twice is a no-op the second time."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)

    await handler.async_device_start_monitoring(mock_input_device)
    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    # Only one connected event should fire
    assert len(events) == 1


async def test_device_stop_monitoring_fires_disconnected_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test stop monitoring fires the disconnected event and cleans up."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)

    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    await handler.async_device_stop_monitoring()
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[CONF_DEVICE_DESCRIPTOR] == FAKE_DEVICE_PATH
    assert events[0].data[CONF_DEVICE_NAME] == FAKE_DEVICE_NAME
    assert handler.dev is None
    assert handler._monitor_task is None
    mock_input_device.close.assert_called_once()


async def test_device_stop_monitoring_noop_when_not_started(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stop monitoring is a no-op when not currently monitoring."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)

    await handler.async_device_stop_monitoring()
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_device_stop_monitoring_ungrab_oserror(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test stop monitoring suppresses OSError from ungrab."""
    mock_config_entry.add_to_hass(hass)
    mock_input_device.ungrab.side_effect = OSError("Permission denied")
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]

    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    # Should not raise despite OSError from ungrab
    await handler.async_device_stop_monitoring()
    await hass.async_block_till_done()

    assert handler.dev is None


# --- DeviceHandler input monitoring tests ---


async def test_monitor_input_fires_key_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test key events from device fire HA bus events."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)

    # key_up event (value=0), which is in default key_types
    key_event = make_key_event(event_type=EV_KEY, code=30, value=KEY_VALUE["key_up"])
    mock_input_device.async_read_loop.return_value = MockAsyncIterator([key_event])

    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[KEY_CODE] == 30
    assert events[0].data["type"] == "key_up"
    assert events[0].data[CONF_DEVICE_DESCRIPTOR] == FAKE_DEVICE_PATH
    assert events[0].data[CONF_DEVICE_NAME] == FAKE_DEVICE_NAME


async def test_monitor_input_ignores_non_key_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test non-EV_KEY events are ignored."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)

    # Non-key event (type=2 is EV_REL for relative movement)
    non_key_event = make_key_event(event_type=2, code=0, value=1)
    mock_input_device.async_read_loop.return_value = MockAsyncIterator([non_key_event])

    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_monitor_input_filters_unconfigured_key_types(
    hass: HomeAssistant,
    mock_input_device: MagicMock,
) -> None:
    """Test key events for unconfigured key types do not fire HA events."""
    # Config only monitors key_up (value=0)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_BY_ID_BASENAME,
        data={
            CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
            CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
        },
        options={
            CONF_KEY_TYPES: ["key_up"],
            CONF_EMULATE_KEY_HOLD: False,
            CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
            CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[entry.entry_id]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)

    # key_down event (value=1) — not in configured key_types
    key_event = make_key_event(event_type=EV_KEY, code=30, value=KEY_VALUE["key_down"])
    mock_input_device.async_read_loop.return_value = MockAsyncIterator([key_event])

    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    assert len(events) == 0


async def test_monitor_input_emulate_key_hold(
    hass: HomeAssistant,
    mock_input_device: MagicMock,
) -> None:
    """Test key hold emulation creates and cancels repeat tasks."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_BY_ID_BASENAME,
        data={
            CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
            CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
        },
        options={
            CONF_KEY_TYPES: ["key_up", "key_down"],
            CONF_EMULATE_KEY_HOLD: True,
            CONF_EMULATE_KEY_HOLD_DELAY: 0.01,
            CONF_EMULATE_KEY_HOLD_REPEAT: 0.01,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[entry.entry_id]
    hold_events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)

    # key_down starts repeat, then key_up cancels it
    key_down = make_key_event(event_type=EV_KEY, code=30, value=KEY_VALUE["key_down"])
    key_up = make_key_event(event_type=EV_KEY, code=30, value=KEY_VALUE["key_up"])
    mock_input_device.async_read_loop.return_value = MockAsyncIterator(
        [key_down, key_up]
    )

    await handler.async_device_start_monitoring(mock_input_device)
    # Let the monitor loop and any repeat tasks process
    await hass.async_block_till_done()

    # We should have at least the key_down and key_up events
    key_down_events = [e for e in hold_events if e.data["type"] == "key_down"]
    key_up_events = [e for e in hold_events if e.data["type"] == "key_up"]
    assert len(key_down_events) >= 1
    assert len(key_up_events) >= 1


async def test_monitor_input_oserror_cleanup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test OSError during monitoring releases the handler."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]

    # Make async_read_loop return an async iterator that raises OSError
    async def _raise_oserror():
        raise OSError("Device removed")
        yield  # pylint: disable=unreachable

    mock_input_device.async_read_loop.return_value = _raise_oserror()

    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    assert handler.is_monitoring is False
    assert handler._monitor_task is None
    assert handler.dev is None


async def test_monitor_input_oserror_cancels_repeat_tasks(
    hass: HomeAssistant,
    mock_input_device: MagicMock,
) -> None:
    """Test OSError during monitoring cancels active key repeat tasks."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_BY_ID_BASENAME,
        data={
            CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
            CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
        },
        options={
            CONF_KEY_TYPES: ["key_down"],
            CONF_EMULATE_KEY_HOLD: True,
            CONF_EMULATE_KEY_HOLD_DELAY: 999,
            CONF_EMULATE_KEY_HOLD_REPEAT: 999,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[entry.entry_id]

    # Yield a key_down (starts a repeat task), then raise OSError
    key_down = make_key_event(event_type=EV_KEY, code=30, value=KEY_VALUE["key_down"])

    async def _key_then_oserror():
        yield key_down
        raise OSError("Device removed")

    mock_input_device.async_read_loop.return_value = _key_then_oserror()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    manager._active_handlers_by_descriptor[FAKE_DEVICE_REAL_PATH] = handler

    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    # The handler is released rather than left looking like it is still
    # monitoring, so a later device event can rebind it
    assert handler._monitor_task is None
    assert handler.is_monitoring is False
    assert FAKE_DEVICE_REAL_PATH not in manager._active_handlers_by_descriptor
    mock_input_device.close.assert_called_once()


async def test_devices_are_released_on_hass_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test shutdown ungrabs and closes devices.

    Config entries are not unloaded when Home Assistant stops, so without a
    stop listener the monitor task is cancelled with the device still grabbed.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]
    await handler.async_device_start_monitoring(mock_input_device)
    manager._active_handlers_by_descriptor[FAKE_DEVICE_REAL_PATH] = handler
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_input_device.ungrab.assert_called_once()
    mock_input_device.close.assert_called_once()
    assert not manager._active_handlers_by_descriptor


# --- KeyboardRemoteManager tests ---


async def test_get_handler_for_device_oserror(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _get_handler_for_device returns (None, None) on OSError."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]

    with patch("evdev.InputDevice", side_effect=OSError("Permission denied")):
        result = manager._get_handler_for_device("/dev/input/event5", [handler])

    assert result == (None, None)


async def test_get_handler_for_device_match(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test _get_handler_for_device returns device and handler on match."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]

    with (
        patch("evdev.InputDevice", return_value=mock_input_device),
        patch.object(handler, "match_rank", return_value=MATCH_DEVICE_PATH),
    ):
        dev, matched = manager._get_handler_for_device(FAKE_DEVICE_REAL_PATH, [handler])

    assert dev is mock_input_device
    assert matched is handler


async def test_get_handler_for_device_no_match(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test _get_handler_for_device closes device and returns (None, None) when no match."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    manager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]

    with (
        patch("evdev.InputDevice", return_value=mock_input_device),
        patch.object(handler, "match_rank", return_value=None),
    ):
        result = manager._get_handler_for_device("/dev/input/event99", [handler])

    assert result == (None, None)
    mock_input_device.close.assert_called_once()


async def test_scan_initial_devices_finds_matching_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test initial device scan starts monitoring for matching devices."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)

    with (
        patch("evdev.list_devices", return_value=[FAKE_DEVICE_REAL_PATH]),
        patch("evdev.InputDevice", return_value=mock_input_device),
        patch.object(handler, "match_rank", return_value=MATCH_DEVICE_PATH),
    ):
        await manager._async_scan_initial_devices()
        await hass.async_block_till_done()

    assert FAKE_DEVICE_REAL_PATH in manager._active_handlers_by_descriptor
    assert len(events) == 1


async def test_scan_initial_devices_skips_non_matching(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test initial device scan skips devices with no matching handler."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)

    with (
        patch("evdev.list_devices", return_value=["/dev/input/event99"]),
        patch("evdev.InputDevice", return_value=mock_input_device),
        patch.object(
            list(manager._handlers.values())[0], "match_rank", return_value=None
        ),
    ):
        await manager._async_scan_initial_devices()
        await hass.async_block_till_done()

    assert len(manager._active_handlers_by_descriptor) == 0
    assert len(events) == 0


async def test_monitor_devices_create_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
    mock_inotify: MagicMock,
) -> None:
    """Test inotify CREATE event starts monitoring for a new device."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)

    # Configure inotify to yield a CREATE event then stop
    inotify_event = MagicMock()
    inotify_event.name = "event5"
    inotify_event.mask = Mask.CREATE

    inotify_iter = MockAsyncIterator([inotify_event])
    mock_inotify.__aiter__ = MagicMock(return_value=inotify_iter)
    mock_inotify.__anext__ = inotify_iter.__anext__

    with (
        patch("evdev.InputDevice", return_value=mock_input_device),
        patch.object(handler, "match_rank", return_value=MATCH_DEVICE_PATH),
    ):
        # Run the monitor loop directly
        await manager._async_monitor_devices()
        await hass.async_block_till_done()

    assert "/dev/input/event5" in manager._active_handlers_by_descriptor
    assert len(events) == 1


async def test_monitor_devices_create_ignored_while_handler_active(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
    mock_inotify: MagicMock,
) -> None:
    """Test a second node is not mapped to a handler that already has a device.

    Mapping it would make a later DELETE of that node stop the device the
    handler is actually reading from.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]

    handler.dev = mock_input_device
    handler._descriptor = FAKE_DEVICE_PATH
    handler._monitor_task = hass.async_create_task(asyncio.sleep(0))
    manager._active_handlers_by_descriptor["/dev/input/event5"] = handler

    sibling = MagicMock()
    sibling.name = FAKE_DEVICE_NAME
    sibling.path = "/dev/input/event9"

    inotify_event = MagicMock()
    inotify_event.name = "event9"
    inotify_event.mask = Mask.CREATE
    inotify_iter = MockAsyncIterator([inotify_event])
    mock_inotify.__aiter__ = MagicMock(return_value=inotify_iter)
    mock_inotify.__anext__ = inotify_iter.__anext__

    with (
        patch("evdev.InputDevice", return_value=sibling),
        patch.object(handler, "match_rank", return_value=MATCH_DEVICE_PATH),
    ):
        await manager._async_monitor_devices()
        await hass.async_block_till_done()

    assert "/dev/input/event9" not in manager._active_handlers_by_descriptor
    assert manager._active_handlers_by_descriptor["/dev/input/event5"] is handler
    sibling.close.assert_called_once()


async def test_monitor_devices_create_ignored_after_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
    mock_inotify: MagicMock,
) -> None:
    """Test a handler unregistered during the executor call is not started."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]

    inotify_event = MagicMock()
    inotify_event.name = "event5"
    inotify_event.mask = Mask.CREATE
    inotify_iter = MockAsyncIterator([inotify_event])
    mock_inotify.__aiter__ = MagicMock(return_value=inotify_iter)
    mock_inotify.__anext__ = inotify_iter.__anext__

    def _open_and_unload(path: str) -> MagicMock:
        # Unload the entry while the executor job is still running
        manager._handlers.clear()
        return mock_input_device

    with (
        patch("evdev.InputDevice", side_effect=_open_and_unload),
        patch.object(handler, "match_rank", return_value=MATCH_DEVICE_PATH),
    ):
        await manager._async_monitor_devices()
        await hass.async_block_till_done()

    assert not manager._active_handlers_by_descriptor
    mock_input_device.close.assert_called_once()


async def test_monitor_devices_delete_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
    mock_inotify: MagicMock,
) -> None:
    """Test inotify DELETE event stops monitoring for a device."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]

    # Manually set up an active handler to simulate a connected device
    handler.dev = mock_input_device
    handler._descriptor = FAKE_DEVICE_PATH
    handler._monitor_task = hass.async_create_task(asyncio.sleep(999))
    manager._active_handlers_by_descriptor["/dev/input/event5"] = handler

    disconnect_events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)

    # Configure inotify to yield a DELETE event then stop
    inotify_event = MagicMock()
    inotify_event.name = "event5"
    inotify_event.mask = Mask.DELETE

    inotify_iter = MockAsyncIterator([inotify_event])
    mock_inotify.__aiter__ = MagicMock(return_value=inotify_iter)
    mock_inotify.__anext__ = inotify_iter.__anext__

    await manager._async_monitor_devices()
    await hass.async_block_till_done()

    assert "/dev/input/event5" not in manager._active_handlers_by_descriptor
    assert len(disconnect_events) == 1


async def test_monitor_devices_create_no_match(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_inotify: MagicMock,
) -> None:
    """Test inotify CREATE event with no matching handler is ignored."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]

    inotify_event = MagicMock()
    inotify_event.name = "event99"
    inotify_event.mask = Mask.CREATE

    inotify_iter = MockAsyncIterator([inotify_event])
    mock_inotify.__aiter__ = MagicMock(return_value=inotify_iter)
    mock_inotify.__anext__ = inotify_iter.__anext__

    with patch("evdev.InputDevice", side_effect=OSError("No device")):
        await manager._async_monitor_devices()
        await hass.async_block_till_done()

    assert "/dev/input/event99" not in manager._active_handlers_by_descriptor


async def test_async_stop_with_active_handlers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test async_stop stops all active device handlers."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]

    # Manually set up an active handler
    handler.dev = mock_input_device
    handler._descriptor = FAKE_DEVICE_PATH
    handler._monitor_task = hass.async_create_task(asyncio.sleep(999))
    manager._active_handlers_by_descriptor[FAKE_DEVICE_REAL_PATH] = handler

    disconnect_events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)

    await manager.async_stop()
    await hass.async_block_till_done()

    assert len(manager._active_handlers_by_descriptor) == 0
    assert not manager._started
    assert len(disconnect_events) == 1


async def test_async_stop_cancels_running_monitor_task(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_stop cancels a still-running monitor task."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]

    # Replace the monitor task with one that is still running
    manager._monitor_task = hass.async_create_task(asyncio.sleep(999))
    assert not manager._monitor_task.done()

    await manager.async_stop()
    await hass.async_block_till_done()

    assert manager._monitor_task is None
    assert not manager._started


async def test_unregister_handler_with_active_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test unregister_handler removes active handler and stops monitoring."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]
    entry_id = mock_config_entry.entry_id

    # Manually set up active handler
    handler.dev = mock_input_device
    handler._descriptor = FAKE_DEVICE_PATH
    handler._monitor_task = hass.async_create_task(asyncio.sleep(999))
    manager._active_handlers_by_descriptor[FAKE_DEVICE_REAL_PATH] = handler

    await manager.unregister_handler(entry_id)
    await hass.async_block_till_done()

    assert entry_id not in manager._handlers
    assert FAKE_DEVICE_REAL_PATH not in manager._active_handlers_by_descriptor


async def test_check_handler_finds_device_after_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test _async_check_handler finds and connects a device for a new handler."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)

    with (
        patch("evdev.list_devices", return_value=[FAKE_DEVICE_REAL_PATH]),
        patch("evdev.InputDevice", return_value=mock_input_device),
        patch.object(handler, "match_rank", return_value=MATCH_DEVICE_PATH),
    ):
        await manager._async_check_handler(handler)
        await hass.async_block_till_done()

    assert FAKE_DEVICE_REAL_PATH in manager._active_handlers_by_descriptor
    assert len(events) == 1


async def test_check_handler_skips_already_active(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test _async_check_handler skips descriptors that are already active."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]
    handler = list(manager._handlers.values())[0]

    # Pre-populate an active handler for this descriptor
    manager._active_handlers_by_descriptor[FAKE_DEVICE_REAL_PATH] = handler
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)

    with patch("evdev.list_devices", return_value=[FAKE_DEVICE_REAL_PATH]):
        await manager._async_check_handler(handler)
        await hass.async_block_till_done()

    # No new connected event since the descriptor was already active
    assert len(events) == 0


async def test_monitor_devices_cancelled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_inotify: MagicMock,
) -> None:
    """Test _async_monitor_devices handles CancelledError gracefully."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    manager: KeyboardRemoteManager = hass.data[DOMAIN]

    # Replace inotify with an async iterator that blocks indefinitely
    started = asyncio.Event()

    class BlockingInotify:
        """Async iterator that blocks on first iteration until cancelled."""

        def __aiter__(self):
            return self

        async def __anext__(self):
            started.set()
            await asyncio.sleep(999)  # block until cancelled

        def rm_watch(self, watch):
            """Accept teardown, which runs when the entry unloads."""

        def close(self):
            """Accept teardown, which runs when the entry unloads."""

    manager._inotify = BlockingInotify()

    task = hass.async_create_task(manager._async_monitor_devices())
    await started.wait()  # ensure the loop has started

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert task.done()


async def test_keyrepeat_fires_hold_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test _async_keyrepeat fires key_hold events on a timer."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    handler = hass.data[DOMAIN]._handlers[mock_config_entry.entry_id]
    handler.dev = mock_input_device
    handler._descriptor = FAKE_DEVICE_PATH

    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)

    # Start keyrepeat with very short delays
    task = hass.async_create_task(
        handler._async_keyrepeat(mock_input_device, 30, 0.001, 0.001)
    )
    # Let it fire a few events
    await asyncio.sleep(0.02)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    await hass.async_block_till_done()

    # Should have fired at least one key_hold event
    hold_events = [e for e in events if e.data["type"] == "key_hold"]
    assert len(hold_events) >= 1
    assert hold_events[0].data[KEY_CODE] == 30
    assert hold_events[0].data[CONF_DEVICE_DESCRIPTOR] == FAKE_DEVICE_PATH
