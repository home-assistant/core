"""Fixtures for Keyboard Remote integration."""

from __future__ import annotations

import asyncio
import collections
from collections.abc import AsyncGenerator, Generator
from unittest.mock import patch

import aionotify
from evdev import InputEvent, ecodes
import pytest

from homeassistant.components.keyboard_remote import (
    DOMAIN,
    KEYBOARD_REMOTE_CONNECTED,
    KEYBOARD_REMOTE_DISCONNECTED,
)
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

WatcherEvent = collections.namedtuple("Event", ["name", "flags", "cookie", "alias"])


class InputDeviceInterface:
    """Duck typing interface to mock evdev.InputDevice."""

    def create_event(self, path: str, code: int, value: int) -> None:
        """Create a new event."""


class WatcherInterface:
    """Duck typing interface to mock aionotify.Watcher."""

    def create_event(self, name: str, flags: int) -> None:
        """Create a new event."""


class MockManager:
    """Manager for mock object needed to test keyboard_remote."""

    def __init__(self):
        """Initialize MockManager."""
        self._evdev_devices: list[InputDeviceInterface] = []
        self._aionotify_watcher: WatcherInterface | None = None

    @property
    def active(self) -> bool:
        """Return if manager is is active."""
        return len(self._evdev_devices) > 0

    def add_evdev_device(self, device: InputDeviceInterface) -> None:
        """Add a new managed evdev device."""
        self._evdev_devices.append(device)

    def create_evdev_event(self, path: str, code: int, value: int) -> None:
        """Create a new evdev event (simulated keyboard action)."""
        for device in self._evdev_devices:
            device.create_event(path, code, value)

    def add_aionotify_watcher(self, watcher: WatcherInterface) -> None:
        """Add a new managed aionotify watcher."""
        self._aionotify_watcher = watcher

    def create_aionotify_event(self, name: str, flags: int) -> None:
        """Create a new aionotify event (simulated usb plug/unplug)."""
        self._aionotify_watcher.create_event(name, flags)

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        self._evdev_devices.clear()


def create_input_device(manager: MockManager, devices: dict[str, dict[str, str]]):
    """Create a mock evdev.InputDevice."""

    class InputDevice(InputDeviceInterface):
        """Class for mock evdev.InputDevice."""

        def __init__(self, path):
            if path not in devices:
                raise OSError
            self.path: str = devices[path]["path"]
            self.name: str = devices[path]["name"]
            self.event: InputEvent | None = None
            manager.add_evdev_device(self)

        def create_event(self, path: str, code: int, value: int) -> None:
            """Create a new event (simulated keyboard action)."""
            if path == self.path:
                self.event = InputEvent(1, 2, ecodes.EV_KEY, code, value)

        def async_read_loop(self) -> AsyncGenerator:
            """Iterate events created in create_event()."""
            return self._async_read_loop()

        async def _async_read_loop(self) -> AsyncGenerator:
            while manager.active:
                if self.event:
                    yield self.event
                    self.event = None
                await asyncio.sleep(0.005)

        @staticmethod
        def fileno() -> int:
            """Mock call."""
            return 0

        def __getattr__(self, name):
            """Mock unimplemented methods."""

            def func(*args, **kwargs):
                """Mock call."""

            return func

    return InputDevice


def create_watcher(manager: MockManager):
    """Create a mock aionotify.Watcher."""

    class Watcher(WatcherInterface):
        """Class for mock aionotify.Watcher."""

        def __init__(self):
            self.event: aionotify.base.Event | None = None
            manager.add_aionotify_watcher(self)

        def create_event(self, name: str, flags: int) -> None:
            """Create a new event (simulated keyboard action)."""
            self.event = WatcherEvent(name=name, flags=flags, cookie="", alias="")

        async def get_event(self) -> aionotify.base.Event:
            """Return events as they are generated in create_event()."""
            while manager.active:
                if self.event:
                    event = self.event
                    self.event = None
                    return event
                await asyncio.sleep(0.005)
            raise asyncio.CancelledError

        async def setup(self, *args, **kwargs) -> None:
            """Mock call."""

        def __getattr__(self, name):
            """Mock unimplemented methods."""

            def func(*args, **kwargs):
                """Mock call."""

            return func

    return Watcher


@pytest.fixture
def mock_manager(request: pytest.FixtureRequest) -> Generator[None, MockManager, None]:
    """Return a manager for creating evdev device and aionotify watcher events."""
    devices: dict[str, dict[str, str]] = {}
    paths: list[str] = []

    if hasattr(request, "param"):
        devices = {p["path"]: p for p in request.param}
        paths = [p["path"] for p in request.param]

    def realpath(path) -> str:
        """Mock os.path.realpath."""
        for device in devices.values():
            if "symlink" in device and device["symlink"] == path:
                return device["path"]
        return path

    with MockManager() as manager:
        with patch(
            "homeassistant.components.keyboard_remote.list_devices", return_value=paths
        ), patch(
            "homeassistant.components.keyboard_remote.InputDevice",
            side_effect=create_input_device(manager, devices),
        ), patch(
            "aionotify.Watcher", side_effect=create_watcher(manager)
        ), patch(
            "os.path.realpath", side_effect=realpath
        ):
            yield manager


@pytest.fixture
async def keyboard_remote(
    hass: HomeAssistant, request: pytest.FixtureRequest
) -> Generator[None, None, None]:
    """Create a pre-configured keyboard_remote integration."""

    config = []
    if hasattr(request, "param"):
        config = request.param

    # Setup keyboard_remote integration
    await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()

    # Trigger keyboard_remote start
    listener = create_bus_signal(hass, KEYBOARD_REMOTE_CONNECTED)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    # Can't use hass.async_block_till_done() since keyboard_remote integration uses loop
    await asyncio.wait_for(listener.wait(), 1)

    yield

    listener = create_bus_signal(hass, KEYBOARD_REMOTE_DISCONNECTED)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()


def create_bus_signal(
    hass: HomeAssistant, name: str, data: dict | None = None
) -> asyncio.Event:
    """Create signal for hass bus events."""

    if data is not None:
        data.clear()

    signal = asyncio.Event()

    async def listener(event) -> None:
        nonlocal data
        if data is not None:
            data.update(event.data)
        signal.set()

    hass.bus.async_listen(name, listener)

    return signal
