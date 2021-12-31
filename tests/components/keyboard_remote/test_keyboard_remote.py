"""Tests for Keyboard Remote config entry."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import aionotify
import pytest

from homeassistant.components.keyboard_remote import (
    DOMAIN,
    KEY_VALUE,
    KEYBOARD_REMOTE_COMMAND_RECEIVED,
    KEYBOARD_REMOTE_CONNECTED,
    KEYBOARD_REMOTE_DISCONNECTED,
)
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MockManager, create_bus_signal

from tests.common import assert_setup_component

KEY_DOWN = KEY_VALUE["key_down"]
KEY_UP = KEY_VALUE["key_up"]
KEY_HOLD = KEY_VALUE["key_hold"]


async def test_config_empty(hass: HomeAssistant) -> None:
    """Test setup ignored with empty config."""
    config = []
    with assert_setup_component(0, DOMAIN) as handle_config:
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    assert not handle_config[DOMAIN]


async def test_config_single_device(hass: HomeAssistant) -> None:
    """Test setup succeeds with single device in config."""
    config = [{"device_descriptor": "/dev/input/event2", "type": ["key_up"]}]
    with assert_setup_component(1, DOMAIN) as handle_config:
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    assert handle_config[DOMAIN]


async def test_config_multiple_devices(hass: HomeAssistant) -> None:
    """Test setup succeeds with multiple devices in config."""
    config = [
        {"device_descriptor": "/dev/input/event1", "type": ["key_up"]},
        {"device_name": "USB Keyboard", "type": ["key_up"]},
    ]
    with assert_setup_component(2, DOMAIN) as handle_config:
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    assert handle_config[DOMAIN]


async def test_config_conflicting_params(hass: HomeAssistant) -> None:
    """Test setup fails with conflicting config params."""
    config = [
        {
            "device_descriptor": "/dev/input/event1",
            "device_name": "USB Keyboard",
            "type": ["key_up"],
        }
    ]
    with assert_setup_component(0, DOMAIN) as handle_config:
        await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    assert not handle_config[DOMAIN]


async def test_config_bad_type(hass: HomeAssistant) -> None:
    """Test setup fails with bad config type param."""
    config = [{"device_descriptor": "/dev/input/event1", "type": ["key_bad"]}]
    with assert_setup_component(0, DOMAIN) as handle_config:
        await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    assert not handle_config[DOMAIN]


async def test_setup_bad_descriptor(
    hass: HomeAssistant, mock_manager: MockManager
) -> None:
    """Test setup fails with non-existent descriptor."""
    with patch(
        "homeassistant.components.keyboard_remote.list_devices",
        return_value=["/dev/input/notfound"],
    ):
        # Setup keyboard_remote
        config = [{"device_descriptor": "/dev/input/event1", "type": ["key_up"]}]
        with assert_setup_component(1, DOMAIN) as handle_config:
            await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        assert handle_config[DOMAIN]
        await hass.async_block_till_done()

        # Attempt startup
        listener = create_bus_signal(hass, KEYBOARD_REMOTE_CONNECTED)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

        # Assert didn't start
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(listener.wait(), 0.05)


@pytest.mark.parametrize(
    "mock_manager,keyboard_remote",
    [
        (
            [  # mock_manager config
                {"path": "/dev/input/event1", "name": "USB Other"},
                {"path": "/dev/input/event2", "name": "Test USB Keyboard"},
                {"path": "/dev/input/event3", "name": "Test USB System Control"},
                {"path": "/dev/input/event4", "name": "Test Named USB Keyboard"},
                {
                    "path": "/dev/input/event5",
                    "name": "Test Symlinked USB Keyboard",
                    "symlink": "/dev/input/by-id/usb-Symlinked-event-kbd",
                },
            ],
            [  # keyboard_remote config
                {
                    "device_descriptor": "/dev/input/event2",
                    "type": ["key_down", "key_up", "key_hold"],
                },
                {"device_descriptor": "/dev/input/event3", "type": ["key_down"]},
                {"device_name": "Test Named USB Keyboard", "type": ["key_down"]},
                {
                    "device_descriptor": "/dev/input/by-id/usb-Symlinked-event-kbd",
                    "type": ["key_down"],
                },
            ],
        )
    ],
    indirect=True,
)
async def test_command_basic(
    hass: HomeAssistant, mock_manager: MockManager, keyboard_remote: None
) -> None:
    """Test keyboard commands."""
    data: dict[str, str] = {}
    signal = create_bus_signal(hass, KEYBOARD_REMOTE_COMMAND_RECEIVED, data)

    # Test event1 key_down ignored (since event1 not being listened to)
    signal.clear()
    mock_manager.create_evdev_event("/dev/input/event1", 32, KEY_DOWN)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(signal.wait(), 0.05)

    # Test event2 key_down received
    mock_manager.create_evdev_event("/dev/input/event2", 30, KEY_DOWN)
    await asyncio.wait_for(signal.wait(), 0.2)
    assert data["key_code"] == 30
    assert data["type"] == "key_down"
    assert data["device_descriptor"] == "/dev/input/event2"
    assert data["device_name"] == "Test USB Keyboard"

    # Test event2 key_hold received
    signal.clear()
    mock_manager.create_evdev_event("/dev/input/event2", 30, KEY_HOLD)
    await asyncio.wait_for(signal.wait(), 0.2)
    assert data["key_code"] == 30
    assert data["type"] == "key_hold"
    assert data["device_descriptor"] == "/dev/input/event2"
    assert data["device_name"] == "Test USB Keyboard"

    # Test repeated event2 key_hold received
    signal.clear()
    mock_manager.create_evdev_event("/dev/input/event2", 30, KEY_HOLD)
    await asyncio.wait_for(signal.wait(), 0.2)
    assert data["key_code"] == 30
    assert data["type"] == "key_hold"
    assert data["device_descriptor"] == "/dev/input/event2"
    assert data["device_name"] == "Test USB Keyboard"

    # Test event2 key_up received
    signal.clear()
    mock_manager.create_evdev_event("/dev/input/event2", 30, KEY_UP)
    await asyncio.wait_for(signal.wait(), 0.2)
    assert data["key_code"] == 30
    assert data["type"] == "key_up"
    assert data["device_descriptor"] == "/dev/input/event2"
    assert data["device_name"] == "Test USB Keyboard"

    # Test event3 key_down received
    signal.clear()
    mock_manager.create_evdev_event("/dev/input/event3", 31, KEY_DOWN)
    await asyncio.wait_for(signal.wait(), 0.2)
    assert data["key_code"] == 31
    assert data["type"] == "key_down"
    assert data["device_descriptor"] == "/dev/input/event3"
    assert data["device_name"] == "Test USB System Control"

    # Test event3 key_up ignored (since event3 key_up not being listened to)
    signal.clear()
    mock_manager.create_evdev_event("/dev/input/event3", 32, KEY_UP)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(signal.wait(), 0.05)

    # Test named event4 key_down received
    mock_manager.create_evdev_event("/dev/input/event4", 30, KEY_DOWN)
    await asyncio.wait_for(signal.wait(), 0.2)
    assert data["key_code"] == 30
    assert data["type"] == "key_down"
    assert data["device_descriptor"] == "/dev/input/event4"
    assert data["device_name"] == "Test Named USB Keyboard"

    # Test symlinked event5 key_down works
    signal.clear()
    mock_manager.create_evdev_event("/dev/input/event5", 32, KEY_DOWN)
    await asyncio.wait_for(signal.wait(), 0.2)
    assert data["key_code"] == 32
    assert data["device_descriptor"] == "/dev/input/event5"
    assert data["device_name"] == "Test Symlinked USB Keyboard"


@pytest.mark.parametrize(
    "mock_manager,keyboard_remote",
    [
        (
            [  # mock_manager config
                {"path": "/dev/input/event2", "name": "Test USB Keyboard"}
            ],
            [  # keyboard_remote config
                {
                    "device_descriptor": "/dev/input/event2",
                    "type": ["key_down", "key_up"],
                    "emulate_key_hold_repeat": 0.1,
                    "emulate_key_hold": True,
                    "emulate_key_hold_delay": 0.01,
                }
            ],
        )
    ],
    indirect=True,
)
async def test_command_emulated_hold(
    hass: HomeAssistant, mock_manager: MockManager, keyboard_remote: None
) -> None:
    """Test emulated hold keyboard commands."""
    data: dict[str, str] = {}
    signal = create_bus_signal(hass, KEYBOARD_REMOTE_COMMAND_RECEIVED, data)

    # Test event2 key_down
    mock_manager.create_evdev_event("/dev/input/event2", 30, KEY_DOWN)
    await asyncio.wait_for(signal.wait(), 0.2)
    assert data["key_code"] == 30
    assert data["type"] == "key_down"
    assert data["device_descriptor"] == "/dev/input/event2"

    # Test event2 key_hold automatically generated
    signal.clear()
    await asyncio.wait_for(signal.wait(), 0.015)  # wait at least emulate_key_hold_delay
    assert data["key_code"] == 30
    assert data["type"] == "key_hold"
    assert data["device_descriptor"] == "/dev/input/event2"

    # Test event2 key_up
    signal.clear()
    mock_manager.create_evdev_event("/dev/input/event2", 30, KEY_UP)
    await asyncio.wait_for(signal.wait(), 0.2)
    assert data["key_code"] == 30
    assert data["type"] == "key_up"
    assert data["device_descriptor"] == "/dev/input/event2"

    # Test event2 key_hold is canceled on teardown
    signal.clear()
    mock_manager.create_evdev_event("/dev/input/event2", 30, KEY_DOWN)
    await asyncio.wait_for(signal.wait(), 0.2)


@pytest.mark.parametrize(
    "mock_manager,keyboard_remote",
    [
        (
            [  # mock_manager config
                {"path": "/dev/input/event2", "name": "Test USB Keyboard"},
                {"path": "/dev/input/event3", "name": "Test Other USB Keyboard"},
            ],
            [  # keyboard_remote config
                {"device_descriptor": "/dev/input/event2", "type": ["key_down"]},
            ],
        )
    ],
    indirect=True,
)
async def test_device_monitor(
    hass: HomeAssistant, mock_manager: MockManager, keyboard_remote: None
) -> None:
    """Test device monitoring."""
    data = {}
    signal = create_bus_signal(hass, KEYBOARD_REMOTE_COMMAND_RECEIVED, data)

    connect_data = {}
    connect_signal = create_bus_signal(hass, KEYBOARD_REMOTE_CONNECTED, connect_data)

    disconnect_data = {}
    disconnect_signal = create_bus_signal(
        hass, KEYBOARD_REMOTE_DISCONNECTED, disconnect_data
    )

    # Baseline event2 key_down check
    mock_manager.create_evdev_event("/dev/input/event2", 30, KEY_DOWN)
    await asyncio.wait_for(signal.wait(), 0.1)
    assert data["key_code"] == 30
    assert data["device_descriptor"] == "/dev/input/event2"

    # Disconnect /dev/input/event2
    mock_manager.create_aionotify_event("event2", aionotify.Flags.DELETE)
    await asyncio.wait_for(disconnect_signal.wait(), 0.2)
    assert disconnect_data["device_descriptor"] == "/dev/input/event2"

    # Test event2 key_down ignored (since event2 no longer being listened to)
    signal.clear()
    mock_manager.create_evdev_event("/dev/input/event2", 30, KEY_DOWN)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(signal.wait(), 0.05)

    # Reconnect /dev/input/event2
    mock_manager.create_aionotify_event("event2", aionotify.Flags.CREATE)
    await asyncio.wait_for(connect_signal.wait(), 0.2)

    # Test event2 key_down works again
    signal.clear()
    mock_manager.create_evdev_event("/dev/input/event2", 30, KEY_DOWN)
    await asyncio.wait_for(signal.wait(), 0.2)
    assert data["key_code"] == 30
    assert data["device_descriptor"] == "/dev/input/event2"

    # Test events for inputs not in config are ignored
    connect_signal.clear()
    mock_manager.create_aionotify_event("event3", aionotify.Flags.CREATE)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(connect_signal.wait(), 0.05)
