"""Fixtures for Keyboard Remote tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.keyboard_remote.const import (
    CONF_DEVICE_NAME,
    CONF_DEVICE_PATH,
    CONF_EMULATE_KEY_HOLD,
    CONF_EMULATE_KEY_HOLD_DELAY,
    CONF_EMULATE_KEY_HOLD_REPEAT,
    CONF_KEY_TYPES,
    DEFAULT_EMULATE_KEY_HOLD,
    DEFAULT_EMULATE_KEY_HOLD_DELAY,
    DEFAULT_EMULATE_KEY_HOLD_REPEAT,
    DEFAULT_KEY_TYPES,
    DOMAIN,
)

from tests.common import MockConfigEntry

FAKE_DEVICE_PATH = "/dev/input/by-id/usb-Test_Keyboard-event-kbd"
FAKE_DEVICE_NAME = "Test Keyboard"
FAKE_DEVICE_REAL_PATH = "/dev/input/event5"
FAKE_BY_ID_BASENAME = "usb-Test_Keyboard-event-kbd"

FAKE_DEVICE_PATH_2 = "/dev/input/by-id/usb-Test_Remote-event-kbd"
FAKE_DEVICE_NAME_2 = "Test Remote"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_BY_ID_BASENAME,
        title=FAKE_DEVICE_NAME,
        data={
            CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
            CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
        },
        options={
            CONF_KEY_TYPES: DEFAULT_KEY_TYPES,
            CONF_EMULATE_KEY_HOLD: DEFAULT_EMULATE_KEY_HOLD,
            CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
            CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.keyboard_remote.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_input_device() -> MagicMock:
    """Create a mock evdev InputDevice."""
    dev = MagicMock()
    dev.name = FAKE_DEVICE_NAME
    dev.path = FAKE_DEVICE_REAL_PATH
    dev.fileno.return_value = 5
    dev.grab = MagicMock()
    dev.ungrab = MagicMock()
    dev.close = MagicMock()
    return dev
