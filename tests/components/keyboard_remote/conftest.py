"""Fixtures for Keyboard Remote tests."""

import asyncio
from collections.abc import AsyncIterator, Callable, Generator
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
BUS_HOST = 0x19

# The integration only imports evdev inside functions, so the fixture below
# covers every import without touching sys.modules for the whole session.
_mock_ecodes = SimpleNamespace(EV_KEY=EV_KEY, BUS_HOST=BUS_HOST)
_mock_evdev = MagicMock()
_mock_evdev.ecodes = _mock_ecodes


@pytest.fixture(autouse=True)
def mock_evdev_module() -> Generator[None]:
    """Ensure the evdev module is always mocked for these tests."""
    _mock_evdev.reset_mock()
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


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up and unloading config entries."""
    with (
        patch(
            "homeassistant.components.keyboard_remote.async_setup_entry",
            return_value=True,
        ) as mock,
        patch(
            "homeassistant.components.keyboard_remote.async_unload_entry",
            return_value=True,
        ),
    ):
        yield mock


class DeviceCall:
    """A device method that runs in the executor, like evdev's C calls.

    Home Assistant's tests run mock targets of async_add_executor_job inline on
    the event loop, so these record their calls as plain callables instead.
    """

    def __init__(
        self, fake: FakeInput, action: Callable[[], None] | None = None
    ) -> None:
        """Initialize, with an optional action run on each successful call."""
        self._fake = fake
        self._action = action
        self._hold: tuple[threading.Event, threading.Event] | None = None
        self.call_count = 0
        self.side_effect: BaseException | None = None

    def __call__(self) -> None:
        """Record the call, wait if held, then fail or run the action."""
        self.call_count += 1
        if (hold := self._hold) is not None:
            self._hold = None
            waiting, release = hold
            waiting.set()
            release.wait(5)
        if self.side_effect is not None:
            raise self.side_effect
        if self._action is not None:
            self._action()

    @property
    def called(self) -> bool:
        """Whether it was called at all."""
        return self.call_count > 0

    def hold(self) -> tuple[threading.Event, threading.Event]:
        """Make the next call wait in the executor until released.

        Returns an event set once the call is waiting, and the one releasing it.
        """
        self._hold = self._fake.new_gate()
        return self._hold

    def assert_called_once(self) -> None:
        """Assert it was called exactly once."""
        assert self.call_count == 1, f"called {self.call_count} times"

    def assert_called(self) -> None:
        """Assert it was called at least once."""
        assert self.call_count > 0, "not called"

    def assert_not_called(self) -> None:
        """Assert it was never called."""
        assert self.call_count == 0, f"called {self.call_count} times"


class _Handle:
    """One open file of a fake device, like each InputDevice evdev returns.

    Calls on it are recorded on the device, so tests assert on the device
    whichever handle the integration used.
    """

    def __init__(self, dev: MagicMock, fd: int) -> None:
        """Open the device with a file descriptor of its own."""
        self._dev = dev
        self._fd = fd
        self.name: str = dev.name
        self.path: str = dev.path
        self.uniq: str = dev.uniq
        self.info = dev.info
        self.grab: DeviceCall = dev.grab
        self.ungrab: DeviceCall = dev.ungrab

    def fileno(self) -> int:
        """Return the file descriptor, -1 once closed like evdev."""
        return self._fd

    def capabilities(self) -> dict[int, list[int]]:
        """Return the device's capabilities."""
        return self._dev.capabilities()

    def async_read_loop(self) -> AsyncIterator[SimpleNamespace]:
        """Read the device's events."""
        return self._dev.async_read_loop()

    def close(self) -> None:
        """Close this handle."""
        self._dev.close()
        self._fd = -1


class _FakeInotify:
    """Inotify whose events come from FakeInput instead of the kernel."""

    def __init__(self, fake: FakeInput) -> None:
        """Initialize with the fake /dev/input it watches."""
        self._fake = fake
        self.queue: asyncio.Queue[SimpleNamespace | BaseException] = asyncio.Queue()
        self.watches: dict[str, SimpleNamespace] = {}
        self.closed = False

    def add_watch(self, path: str, mask: Mask) -> SimpleNamespace:
        """Watch a directory, failing like the kernel would."""
        path = os.fspath(path)
        if (error := self._fake.watch_errors.get(path)) is not None:
            raise error
        # udev creates the by-id directory with its first link
        if path == DEVINPUT_BY_ID and not self._fake.by_id_links:
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
        """Wait for the next emitted event, or raise an emitted error."""
        item = await self.queue.get()
        if isinstance(item, BaseException):
            raise item
        return item


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
        self.listing_error: OSError | None = None
        self.inotify: _FakeInotify | None = None
        self.inotify_instances: list[_FakeInotify] = []
        self.opened: list[str] = []
        self.gates: list[tuple[threading.Event, threading.Event]] = []
        self._next_fd = 100
        self._listing_gate: tuple[threading.Event, threading.Event] | None = None
        self._open_gates: dict[str, tuple[threading.Event, threading.Event]] = {}

    @property
    def by_id_links(self) -> dict[str, str]:
        """The links in /dev/input/by-id, other links like by-path aside."""
        return {
            link: target
            for link, target in self.links.items()
            if link.startswith(f"{DEVINPUT_BY_ID}/")
        }

    def add(
        self,
        path: str,
        name: str,
        *,
        link: str | None = None,
        sends_keys: bool = True,
        bustype: int = BUS_USB,
        uniq: str = "",
    ) -> MagicMock:
        """Add a device that is present before setup, without any events."""
        dev = self._make_device(path, name, sends_keys, bustype, uniq)
        self.devices[path] = dev
        if link is not None:
            self.links[link] = path
        return dev

    def add_unopenable(self, path: str) -> None:
        """Add a node that exists but cannot be opened."""
        self.devices[path] = None

    async def plug(
        self, path: str, name: str, *, link: str | None = None, uniq: str = ""
    ) -> MagicMock:
        """Plug in a device in the order udev reports it.

        The node's CREATE and ATTRIB come first. The by-id link only appears
        after they were handled, together with its directory for the first
        link, and is otherwise renamed into place.
        """
        dev = self._make_device(path, name, True, BUS_USB, uniq)
        self.devices[path] = dev
        self._emit(os.path.basename(path), Mask.CREATE)
        self._emit(os.path.basename(path), Mask.ATTRIB)
        await self.settle()
        if link is not None:
            first_link = not self.by_id_links
            self.links[link] = path
            if first_link:
                self._emit("by-id", Mask.CREATE | Mask.ISDIR)
            else:
                self._emit(os.path.basename(link), Mask.MOVED_TO, DEVINPUT_BY_ID)
            await self.settle()
        return dev

    async def touch(self, path: str, *, wait_for_executor: bool = True) -> None:
        """Report an attribute change on a node, as udev does on permissions."""
        self._emit(os.path.basename(path), Mask.ATTRIB)
        await self.settle(wait_for_executor=wait_for_executor)

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
            not self.by_id_links
            and self.inotify is not None
            and (watch := self.inotify.watches.pop(DEVINPUT_BY_ID, None))
        ):
            # udev removes the directory with its last link
            self._emit(None, Mask.IGNORED, watch=watch)
        await self.settle()

    async def overflow(self) -> None:
        """Report that the kernel dropped events, which names no watch."""
        assert self.inotify is not None
        self.inotify.queue.put_nowait(
            SimpleNamespace(name=None, mask=Mask.Q_OVERFLOW, watch=None)
        )
        await self.settle()

    def remove_node(self, path: str) -> None:
        """Report a node's removal without failing its reads yet."""
        self.devices.pop(path)
        self._emit(os.path.basename(path), Mask.DELETE)

    def new_gate(self) -> tuple[threading.Event, threading.Event]:
        """Return a waiting and a release event, released at teardown at the latest."""
        gate = (threading.Event(), threading.Event())
        self.gates.append(gate)
        return gate

    def hold_listing(self) -> tuple[threading.Event, threading.Event]:
        """Make the next device listing wait in the executor until released.

        Returns an event set once the listing is waiting, and the one releasing
        it.
        """
        self._listing_gate = self.new_gate()
        return self._listing_gate

    def hold_open(self, path: str) -> tuple[threading.Event, threading.Event]:
        """Make the next open of a node wait in the executor until released.

        Returns an event set once the open is waiting, and the one releasing it.
        """
        self._open_gates[path] = self.new_gate()
        return self._open_gates[path]

    async def press(self, dev: MagicMock, code: int, value: int) -> None:
        """Send a key event from a device."""
        await self.send(dev, SimpleNamespace(type=EV_KEY, code=code, value=value))

    async def send(
        self,
        dev: MagicMock,
        event: SimpleNamespace | BaseException,
        *,
        wait_for_executor: bool = True,
    ) -> None:
        """Send an input event, or an exception to raise, from a device."""
        dev.read_queue.put_nowait(event)
        await self.settle(wait_for_executor=wait_for_executor)

    async def settle(self, *, wait_for_executor: bool = True) -> None:
        """Wait until everything emitted so far has been handled.

        Done once no executor job is pending and no callback is scheduled, so
        every task is blocked on something, like a queue or a timer. Executor
        jobs started from background tasks are invisible to
        async_block_till_done, so they are waited for separately. Pass
        wait_for_executor=False while a test holds an executor job, which would
        otherwise be waited for.
        """
        for _ in range(10_000):
            if wait_for_executor:
                await self.hass.async_block_till_done()
                if jobs := self._pending_executor_jobs():
                    await asyncio.wait(jobs)
                    continue
            if self._idle():
                return
            await asyncio.sleep(0)
        raise AssertionError("emitted events were never handled")

    async def wait_until(self, condition: Callable[[], bool]) -> None:
        """Run the event loop until the condition holds."""
        async with asyncio.timeout(5):
            while not condition():
                await asyncio.sleep(0)

    def _tasks(self) -> list[asyncio.Future[Any]]:
        return [*self.hass._tasks, *self.hass._background_tasks]

    def _pending_executor_jobs(self) -> list[asyncio.Future[Any]]:
        return [
            job
            for job in self._tasks()
            if not isinstance(job, asyncio.Task) and not job.done()
        ]

    def _idle(self) -> bool:
        # Every runnable task, and every finished future waking its waiter,
        # has a callback scheduled
        return not self._queued() and not self.hass.loop._ready  # type: ignore[attr-defined]

    def _queued(self) -> bool:
        if self.inotify is not None and not self.inotify.queue.empty():
            return True
        return any(
            dev is not None and not dev.read_queue.empty()
            for dev in self.devices.values()
        )

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
        self, path: str, name: str, sends_keys: bool, bustype: int, uniq: str
    ) -> MagicMock:
        dev = MagicMock()
        dev.name = name
        dev.uniq = uniq
        dev.path = path
        dev.grab = DeviceCall(self)
        dev.ungrab = DeviceCall(self)
        dev.close = DeviceCall(self)
        dev.capabilities.return_value = {EV_KEY if sends_keys else EV_SW: [30]}
        dev.info.bustype = bustype
        dev.read_queue = asyncio.Queue()

        async def _read() -> AsyncIterator[SimpleNamespace]:
            while True:
                item = await dev.read_queue.get()
                if isinstance(item, BaseException):
                    raise item
                yield item

        dev.async_read_loop.side_effect = _read
        return dev

    def _open(self, path: str) -> _Handle:
        path = os.fspath(path)
        if (gate := self._open_gates.pop(path, None)) is not None:
            waiting, release = gate
            waiting.set()
            release.wait(5)
        self.opened.append(path)
        if path not in self.devices:
            raise FileNotFoundError(errno.ENOENT, "No such file or directory", path)
        if (dev := self.devices[path]) is None:
            raise PermissionError(errno.EACCES, "Permission denied", path)
        self._next_fd += 1
        return _Handle(dev, self._next_fd)

    def _list(self, input_device_dir: str = DEVINPUT) -> list[str]:
        if (gate := self._listing_gate) is not None:
            self._listing_gate = None
            waiting, release = gate
            waiting.set()
            release.wait(5)
        if self.listing_error is not None:
            raise self.listing_error
        return list(self.devices)

    def _new_inotify(self) -> _FakeInotify:
        if self.inotify_error is not None:
            raise self.inotify_error
        self.inotify = _FakeInotify(self)
        self.inotify_instances.append(self.inotify)
        return self.inotify


def _devinput_path(path: Any) -> str | None:
    """Return the path as str if it is in /dev/input, else None."""
    if isinstance(path, os.PathLike):
        path = os.fspath(path)
    if isinstance(path, str) and (path == DEVINPUT or path.startswith(f"{DEVINPUT}/")):
        return path
    return None


@pytest.fixture
def fake_input(hass: HomeAssistant) -> Generator[FakeInput]:
    """Provide a fake /dev/input that the integration discovers and watches.

    Only /dev/input paths are faked; any other path goes to the real function.
    """
    fake = FakeInput(hass)
    real_realpath = os.path.realpath
    real_exists = os.path.exists
    real_scandir = os.scandir

    def _realpath(path: Any, *args: Any, **kwargs: Any) -> Any:
        if (devinput := _devinput_path(path)) is not None:
            return fake.links.get(devinput, devinput)
        return real_realpath(path, *args, **kwargs)

    def _exists(path: Any) -> bool:
        if (devinput := _devinput_path(path)) is not None:
            return devinput in fake.links or devinput in fake.devices
        return real_exists(path)

    def _scandir(path: Any = ".") -> Any:
        if _devinput_path(path) == DEVINPUT_BY_ID:
            if fake.by_id_error is not None:
                raise fake.by_id_error
            return nullcontext(
                [
                    SimpleNamespace(
                        path=link,
                        name=os.path.basename(link),
                        is_symlink=lambda: True,
                    )
                    for link in fake.by_id_links
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
        patch("os.scandir", _scandir),
    ):
        try:
            yield fake
        finally:
            # A test that failed while holding an executor job must not leave
            # the thread waiting
            for _waiting, release in fake.gates:
                release.set()
