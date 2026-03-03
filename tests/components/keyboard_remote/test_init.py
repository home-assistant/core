"""Tests for the Keyboard Remote integration init."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

from asyncinotify import Mask
import pytest

from homeassistant.components.keyboard_remote import (
    DeviceHandler,
    KeyboardRemoteManager,
    _async_import_yaml_device,
    async_setup,
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
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir

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


@pytest.fixture(autouse=True)
def mock_inotify():
    """Mock inotify to prevent real filesystem access."""
    with patch(
        "homeassistant.components.keyboard_remote.Inotify",
    ) as mock_cls:
        mock_instance = MagicMock()
        # Make async iteration raise StopAsyncIteration immediately
        mock_instance.__aiter__ = MagicMock(return_value=mock_instance)
        mock_instance.__anext__ = AsyncMock(side_effect=StopAsyncIteration)
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def mock_list_devices():
    """Mock evdev list_devices to return empty list."""
    with patch(
        "evdev.list_devices",
        return_value=[],
    ):
        yield


# --- Setup / unload tests ---


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up a config entry creates the shared manager."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert mock_config_entry.state.name == "LOADED"


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the last config entry removes the shared manager."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN not in hass.data


async def test_multiple_entries_shared_manager(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test multiple entries share one manager, cleanup on last unload."""
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

    assert DOMAIN in hass.data
    manager = hass.data[DOMAIN]

    # Unload first entry — manager should still exist
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert hass.data[DOMAIN] is manager

    # Unload second entry — manager should be cleaned up
    await hass.config_entries.async_unload(entry2.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN not in hass.data


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
) -> None:
    """Test YAML import creates a deprecation repair issue."""
    issue_registry = ir.async_get(hass)

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
) -> None:
    """Test YAML import failure creates an error issue."""
    issue_registry = ir.async_get(hass)

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
    """Test async_setup returns True when DOMAIN not in config."""
    result = await async_setup(hass, {})
    assert result is True


async def test_async_setup_with_yaml_config(hass: HomeAssistant) -> None:
    """Test async_setup creates import tasks for YAML device blocks."""
    with patch(
        "homeassistant.components.keyboard_remote._async_import_yaml_device",
        new_callable=AsyncMock,
    ) as mock_import:
        result = await async_setup(
            hass,
            {
                DOMAIN: [
                    {"device_descriptor": "/dev/input/event5"},
                    {"device_name": "Test Keyboard"},
                ]
            },
        )
        await hass.async_block_till_done()

    assert result is True
    assert mock_import.call_count == 2


# --- DeviceHandler.matches_device tests ---


async def test_matches_device_by_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test matches_device returns True when configured path resolves to same real path."""
    handler = DeviceHandler(hass, mock_config_entry)

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
    handler = DeviceHandler(hass, entry)

    with (
        patch("os.path.realpath", return_value=FAKE_DEVICE_REAL_PATH),
        patch("os.path.exists", return_value=False),
    ):
        assert handler.matches_device(FAKE_DEVICE_REAL_PATH, mock_input_device) is True


async def test_matches_device_by_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test matches_device returns True when device name matches."""
    handler = DeviceHandler(hass, mock_config_entry)

    with (
        patch("os.path.realpath", side_effect=lambda p: p),
        patch("os.path.exists", return_value=False),
    ):
        # Device name matches the config entry's device_name
        assert handler.matches_device("/dev/input/event99", mock_input_device) is True


async def test_matches_device_no_match(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test matches_device returns False when no strategy matches."""
    handler = DeviceHandler(hass, mock_config_entry)
    dev = MagicMock()
    dev.name = "Unknown Device"

    with (
        patch("os.path.realpath", side_effect=lambda p: p),
        patch("os.path.exists", return_value=False),
    ):
        assert handler.matches_device("/dev/input/event99", dev) is False


# --- DeviceHandler start/stop monitoring tests ---


async def test_device_start_monitoring_fires_connected_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test start monitoring fires the connected event with correct data."""
    mock_config_entry.add_to_hass(hass)
    handler = DeviceHandler(hass, mock_config_entry)
    events = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)

    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data[CONF_DEVICE_DESCRIPTOR] == FAKE_DEVICE_PATH
    assert events[0].data[CONF_DEVICE_NAME] == FAKE_DEVICE_NAME
    assert handler.dev is mock_input_device


async def test_device_start_monitoring_idempotent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_input_device: MagicMock,
) -> None:
    """Test calling start monitoring twice is a no-op the second time."""
    mock_config_entry.add_to_hass(hass)
    handler = DeviceHandler(hass, mock_config_entry)
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
    handler = DeviceHandler(hass, mock_config_entry)
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
    handler = DeviceHandler(hass, mock_config_entry)
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
    handler = DeviceHandler(hass, mock_config_entry)

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
    handler = DeviceHandler(hass, mock_config_entry)
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
    handler = DeviceHandler(hass, mock_config_entry)
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
    handler = DeviceHandler(hass, entry)
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
    handler = DeviceHandler(hass, entry)
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
    """Test OSError during monitoring cleans up repeat tasks."""
    mock_config_entry.add_to_hass(hass)
    handler = DeviceHandler(hass, mock_config_entry)

    # Make async_read_loop return an async iterator that raises OSError
    async def _raise_oserror():
        yield  # make it an async generator
        raise OSError("Device removed")

    mock_input_device.async_read_loop.return_value = _raise_oserror()

    await handler.async_device_start_monitoring(mock_input_device)
    await hass.async_block_till_done()

    # Monitor task should complete without raising
    assert handler._monitor_task is not None
    assert handler._monitor_task.done()


# --- KeyboardRemoteManager tests ---


async def test_get_handler_for_device_oserror(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test _get_handler_for_device returns (None, None) on OSError."""
    mock_config_entry.add_to_hass(hass)
    manager = KeyboardRemoteManager(hass)
    handler = DeviceHandler(hass, mock_config_entry)

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
    manager = KeyboardRemoteManager(hass)
    handler = DeviceHandler(hass, mock_config_entry)

    with (
        patch("evdev.InputDevice", return_value=mock_input_device),
        patch.object(handler, "matches_device", return_value=True),
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
    manager = KeyboardRemoteManager(hass)
    handler = DeviceHandler(hass, mock_config_entry)

    with (
        patch("evdev.InputDevice", return_value=mock_input_device),
        patch.object(handler, "matches_device", return_value=False),
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
        patch.object(handler, "matches_device", return_value=True),
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
            list(manager._handlers.values())[0], "matches_device", return_value=False
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
        patch.object(handler, "matches_device", return_value=True),
    ):
        # Run the monitor loop directly
        await manager._async_monitor_devices()
        await hass.async_block_till_done()

    assert "/dev/input/event5" in manager._active_handlers_by_descriptor
    assert len(events) == 1


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
        patch.object(handler, "matches_device", return_value=True),
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
    handler = DeviceHandler(hass, mock_config_entry)
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
