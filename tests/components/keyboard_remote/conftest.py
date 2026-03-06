"""Fixtures for Keyboard Remote tests."""

from __future__ import annotations

from collections.abc import Generator
import sys
from types import SimpleNamespace
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

# Stable evdev constants for tests (must match the constants used in event mocks
# so that mocked events behave consistently with the integration under test)
EV_KEY = 1

# Build a mock evdev module with stable constants before any integration import
_mock_ecodes = SimpleNamespace(EV_KEY=EV_KEY)
_mock_evdev = MagicMock()
_mock_evdev.ecodes = _mock_ecodes
_mock_evdev.categorize = MagicMock(side_effect=lambda e: f"key event {e.code}")

if "evdev" not in sys.modules:
    sys.modules["evdev"] = _mock_evdev


@pytest.fixture(autouse=True)
def mock_evdev_module() -> Generator[None]:
    """Ensure the evdev module is always mocked for these tests."""
    with patch.dict(sys.modules, {"evdev": _mock_evdev}):
        yield


FAKE_DEVICE_PATH = "/dev/input/by-id/usb-Test_Keyboard-event-kbd"
FAKE_DEVICE_NAME = "Test Keyboard"
FAKE_DEVICE_REAL_PATH = "/dev/input/event5"
FAKE_BY_ID_BASENAME = "usb-Test_Keyboard-event-kbd"

FAKE_DEVICE_PATH_2 = "/dev/input/by-id/usb-Test_Remote-event-kbd"
FAKE_DEVICE_NAME_2 = "Test Remote"


class MockAsyncIterator:
    """Reusable async iterator that yields items from a list then stops."""

    def __init__(self, items: list | None = None) -> None:
        """Initialize with a list of items to yield."""
        self._items = list(items) if items else []

    def __aiter__(self) -> MockAsyncIterator:
        """Return self as the async iterator."""
        return self

    async def __anext__(self):
        """Yield next item or stop."""
        if self._items:
            return self._items.pop(0)
        raise StopAsyncIteration


def make_key_event(
    event_type: int = EV_KEY, code: int = 30, value: int = 0
) -> SimpleNamespace:
    """Create a mock evdev key event."""
    return SimpleNamespace(type=event_type, code=code, value=value)


def make_inotify_event(name: str, mask: int) -> SimpleNamespace:
    """Create a mock inotify event."""
    return SimpleNamespace(name=name, mask=mask)


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
    dev.async_read_loop = MagicMock(return_value=MockAsyncIterator())
    return dev
