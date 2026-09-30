"""Fixtures for Keyboard Remote tests."""

import asyncio
from collections.abc import AsyncIterator, Generator
from contextlib import nullcontext
import errno
import os
from pathlib import PurePath
import sys
import threading
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from asyncinotify import Mask
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
    DEVINPUT,
    DEVINPUT_BY_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Stable evdev constants for tests (must match the constants used in event mocks
# so that mocked events behave consistently with the integration under test)
EV_KEY = 1
EV_REL = 2
EV_SW = 5
BUS_USB = 0x03
BUS_BLUETOOTH = 0x05
BUS_HOST = 0x19

# The integration only imports evdev inside functions, so the fixture below
# covers every import without touching sys.modules for the whole session.
_mock_ecodes = SimpleNamespace(EV_KEY=EV_KEY, BUS_HOST=BUS_HOST)
_mock_evdev = MagicMock()
_mock_evdev.ecodes = _mock_ecodes
_mock_evdev.categorize = MagicMock(side_effect=lambda e: f"key event {e.code}")


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


@pytest.fixture(autouse=True)
def mock_inotify() -> Generator[MagicMock]:
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
def mock_list_devices() -> Generator[None]:
    """Mock evdev list_devices to return empty list."""
    with patch(
        "evdev.list_devices",
        return_value=[],
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.keyboard_remote.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


class _FakeInotify:
    """Inotify whose events come from FakeInput instead of the kernel."""

    def __init__(self, fake: FakeInput) -> None:
        """Initialize with the fake /dev/input it watches."""
        self._fake = fake
        self.queue: asyncio.Queue[SimpleNamespace] = asyncio.Queue()
        self.watches: dict[str, SimpleNamespace] = {}
        self.closed = False

    def add_watch(self, path: str, mask: Mask) -> SimpleNamespace:
        """Watch a directory, failing like the kernel would."""
        path = os.fspath(path)
        if (error := self._fake.watch_errors.get(path)) is not None:
            raise error
        # udev creates the by-id directory with its first link
        if path == DEVINPUT_BY_ID and not self._fake.links:
            raise FileNotFoundError(errno.ENOENT, "No such file or directory", path)
        watch = SimpleNamespace(path=path, mask=mask)
        self.watches[path] = watch
        return watch

    def rm_watch(self, watch: SimpleNamespace) -> None:
        """Remove a watch, failing if the kernel already dropped it."""
        if (error := self._fake.rm_watch_errors.get(watch.path)) is not None:
            raise error
        self.watches.pop(watch.path, None)

    def close(self) -> None:
        """Close the instance."""
        self.closed = True

    def __aiter__(self) -> _FakeInotify:
        """Iterate over the emitted events."""
        return self

    async def __anext__(self) -> SimpleNamespace:
        """Wait for the next emitted event."""
        return await self.queue.get()


class FakeInput:
    """A fake /dev/input with hot-pluggable evdev devices.

    Devices are opened, grabbed and read through the mocked evdev module, and
    plugging or unplugging one emits the inotify events udev causes.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize an empty /dev/input."""
        self.hass = hass
        # A device of None exists but cannot be opened
        self.devices: dict[str, MagicMock | None] = {}
        self.links: dict[str, str] = {}
        self.watch_errors: dict[str, OSError] = {}
        self.rm_watch_errors: dict[str, OSError] = {}
        self.inotify_error: OSError | None = None
        self.by_id_error: OSError | None = None
        self.inotify: _FakeInotify | None = None
        self.opened: list[str] = []
        self._next_fd = 100
        self._listing_gate: tuple[threading.Event, threading.Event] | None = None

    def add(
        self,
        path: str,
        name: str,
        *,
        link: str | None = None,
        sends_keys: bool = True,
        bustype: int = BUS_USB,
    ) -> MagicMock:
        """Add a device that is present before setup, without any events."""
        dev = self._make_device(path, name, sends_keys, bustype)
        self.devices[path] = dev
        if link is not None:
            self.links[link] = path
        return dev

    def add_unopenable(self, path: str) -> None:
        """Add a node that exists but cannot be opened."""
        self.devices[path] = None

    async def plug(
        self, path: str, name: str, *, link: str | None = None, wait: bool = True
    ) -> MagicMock:
        """Plug in a device in the order udev reports it.

        The node's CREATE and ATTRIB come first. The by-id link only appears
        after they were handled, together with its directory for the first
        link, and is otherwise renamed into place.
        """
        dev = self._make_device(path, name, True, BUS_USB)
        self.devices[path] = dev
        self._emit(os.path.basename(path), Mask.CREATE)
        self._emit(os.path.basename(path), Mask.ATTRIB)
        if wait:
            await self.settle()
        if link is not None:
            first_link = not self.links
            self.links[link] = path
            if first_link:
                self._emit("by-id", Mask.CREATE | Mask.ISDIR)
            else:
                self._emit(os.path.basename(link), Mask.MOVED_TO, DEVINPUT_BY_ID)
            await self.settle()
        return dev

    async def touch(self, path: str) -> None:
        """Report an attribute change on a node, as udev does on permissions."""
        self._emit(os.path.basename(path), Mask.ATTRIB)
        await self.settle()

    async def link(self, link: str, target: str) -> None:
        """Rename a by-id link into place."""
        self.links[link] = target
        self._emit(os.path.basename(link), Mask.MOVED_TO, DEVINPUT_BY_ID)
        await self.settle()

    async def unplug(self, path: str) -> None:
        """Unplug a device: its read fails, and its node and links go away."""
        dev = self.devices.pop(path)
        for link in [link for link, target in self.links.items() if target == path]:
            del self.links[link]
        assert dev is not None
        dev.read_queue.put_nowait(OSError(errno.ENODEV, "No such device"))
        self._emit(os.path.basename(path), Mask.DELETE)
        if (
            not self.links
            and self.inotify is not None
            and (watch := self.inotify.watches.pop(DEVINPUT_BY_ID, None))
        ):
            # udev removes the directory with its last link
            self._emit(None, Mask.IGNORED, watch=watch)
        await self.settle()

    def remove_node(self, path: str) -> None:
        """Report a node's removal without failing its reads yet."""
        self.devices.pop(path)
        self._emit(os.path.basename(path), Mask.DELETE)

    def hold_ungrab(self, dev: MagicMock) -> tuple[threading.Event, threading.Event]:
        """Make ungrabbing the device wait in the executor until released.

        Returns an event set once ungrab is waiting, and the one releasing it.
        """
        waiting, release = threading.Event(), threading.Event()

        def _ungrab() -> None:
            waiting.set()
            release.wait(5)

        # A plain function runs in the executor like evdev's, where a mock
        # would run inline on the event loop.
        dev.ungrab = _ungrab
        return waiting, release

    def hold_listing(self) -> tuple[threading.Event, threading.Event]:
        """Make the next device listing wait in the executor until released.

        Returns an event set once the listing is waiting, and the one releasing
        it.
        """
        self._listing_gate = (threading.Event(), threading.Event())
        return self._listing_gate

    async def press(self, dev: MagicMock, code: int, value: int) -> None:
        """Send a key event from a device."""
        await self.send(dev, SimpleNamespace(type=EV_KEY, code=code, value=value))

    async def send(self, dev: MagicMock, event: Any, *, wait: bool = True) -> None:
        """Send an input event, or an exception to raise, from a device.

        Pass wait=False while an executor job is held, which settling would
        wait for.
        """
        dev.read_queue.put_nowait(event)
        if wait:
            await self.settle()
        else:
            for _ in range(10):
                await asyncio.sleep(0)

    async def settle(self) -> None:
        """Let the watcher and device monitors handle what was emitted.

        Handling one event can take several rounds: the watcher, an executor
        lookup, then the device monitor starting.
        """
        for _ in range(10):
            await self.hass.async_block_till_done()
            await asyncio.sleep(0)

    def _emit(
        self,
        name: str | None,
        mask: Mask,
        watch_path: str = DEVINPUT,
        watch: SimpleNamespace | None = None,
    ) -> None:
        if self.inotify is None:
            return
        if watch is None:
            watch = self.inotify.watches.get(watch_path)
        if watch is None:
            return
        self.inotify.queue.put_nowait(
            SimpleNamespace(
                name=None if name is None else PurePath(name), mask=mask, watch=watch
            )
        )

    def _make_device(
        self, path: str, name: str, sends_keys: bool, bustype: int
    ) -> MagicMock:
        dev = MagicMock()
        dev.name = name
        dev.path = path
        self._next_fd += 1
        dev.fileno.return_value = self._next_fd
        # Like evdev, a closed device reports fd -1
        dev.close.side_effect = lambda: setattr(dev.fileno, "return_value", -1)
        dev.capabilities.return_value = {EV_KEY if sends_keys else EV_SW: [30]}
        dev.info.bustype = bustype
        dev.read_queue = asyncio.Queue()

        async def _read() -> AsyncIterator[Any]:
            while True:
                item = await dev.read_queue.get()
                if isinstance(item, BaseException):
                    raise item
                yield item

        dev.async_read_loop.side_effect = _read
        return dev

    def _open(self, path: str) -> MagicMock:
        path = os.fspath(path)
        self.opened.append(path)
        if path not in self.devices:
            raise FileNotFoundError(errno.ENOENT, "No such file or directory", path)
        if (dev := self.devices[path]) is None:
            raise PermissionError(errno.EACCES, "Permission denied", path)
        # Each open gets a new file descriptor, as a closed one reports -1
        self._next_fd += 1
        dev.fileno.return_value = self._next_fd
        return dev

    def _list(self, *args: Any) -> list[str]:
        if (gate := self._listing_gate) is not None:
            self._listing_gate = None
            waiting, release = gate
            waiting.set()
            release.wait(5)
        return list(self.devices)

    def _new_inotify(self) -> _FakeInotify:
        if self.inotify_error is not None:
            raise self.inotify_error
        self.inotify = _FakeInotify(self)
        return self.inotify


@pytest.fixture
def fake_input(hass: HomeAssistant, mock_evdev_module: None) -> Generator[FakeInput]:
    """Provide a fake /dev/input that the integration discovers and watches."""
    fake = FakeInput(hass)
    real_realpath = os.path.realpath
    real_exists = os.path.exists
    real_isdir = os.path.isdir
    real_scandir = os.scandir

    def _in_devinput(path: str) -> bool:
        return path == DEVINPUT or path.startswith(f"{DEVINPUT}/")

    def _realpath(path: Any, *args: Any, **kwargs: Any) -> str:
        path = os.fspath(path)
        if _in_devinput(path):
            return fake.links.get(path, path)
        return real_realpath(path, *args, **kwargs)

    def _exists(path: Any) -> bool:
        path = os.fspath(path)
        if _in_devinput(path):
            return path in fake.links or path in fake.devices
        return real_exists(path)

    def _isdir(path: Any) -> bool:
        path = os.fspath(path)
        if path == DEVINPUT_BY_ID:
            return bool(fake.links)
        return real_isdir(path)

    def _scandir(path: Any = ".") -> Any:
        if os.fspath(path) == DEVINPUT_BY_ID:
            if fake.by_id_error is not None:
                raise fake.by_id_error
            return nullcontext(
                [
                    SimpleNamespace(
                        path=link,
                        name=os.path.basename(link),
                        is_symlink=lambda: True,
                    )
                    for link in fake.links
                ]
            )
        return real_scandir(path)

    with (
        patch(
            "homeassistant.components.keyboard_remote.Inotify",
            side_effect=fake._new_inotify,
        ),
        patch("evdev.list_devices", side_effect=fake._list),
        patch("evdev.InputDevice", side_effect=fake._open),
        patch("os.path.realpath", _realpath),
        patch("os.path.exists", _exists),
        patch("os.path.isdir", _isdir),
        patch("os.scandir", _scandir),
    ):
        yield fake
