"""Fixtures for the tests that need a running Home Assistant.

These tests drive the integration over a **real TCP socket** rather than a mocked one. The sprint's
acceptance criteria are about socket behaviour — a reconnect mid-session, a malformed frame, three
panels on one port, the port actually being freed on unload — and a mocked socket cannot fail any of
them. Nothing here binds a fixed port: one is claimed and released just before use, so the suite is
safe to run on a machine that is also running the lab.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
import contextlib
from dataclasses import replace
import socket
from typing import Any
from unittest.mock import patch

from pyjfl import Cmd, FrameReader, PgmRecord
import pytest

from homeassistant.components.jfl_alarm.const import (
    CONF_READ_ONLY,
    CONF_SERIAL,
    DOMAIN,
    SUBENTRY_TYPE_PANEL,
)
from homeassistant.components.jfl_alarm.coordinator import JflPanelCoordinator
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .panel_sim import FakePanel

from tests.common import MockConfigEntry

LOOPBACK = "127.0.0.1"


def free_port() -> int:
    """Claim an unused TCP port and release it again.

    There is an unavoidable race between releasing and rebinding, but binding to a fixed port would
    collide with the developer's own lab, which is a far more likely failure.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOOPBACK, 0))
        return int(probe.getsockname()[1])


@pytest.fixture(autouse=True)
def allow_real_sockets(socket_enabled: None) -> None:
    """Let these tests open real sockets.

    The Home Assistant harness blocks `socket.socket` by default, and rightly so — a unit test that
    reaches the network is a flaky test. Here the socket *is* the subject: this integration exists
    to listen on one, and the sprint's acceptance criteria are about what happens on it. Everything
    bound stays on the loopback interface.
    """


@pytest.fixture(autouse=True)
def slow_status_poll() -> Generator[None]:
    """Stretch the status-poll interval so `_poll_forever` never fires mid-test.

    `status_interval` is not user-configurable — every entry gets `DEFAULT_STATUS_INTERVAL` — so a
    suite that left it at 30 seconds would still be short enough for a slow CI run to catch a real
    poll landing between a test's own status frame and its assertions. Patched to an hour instead of
    threaded through `make_entry`, because nothing about the setting is per-entry anymore.
    """
    with patch("homeassistant.components.jfl_alarm.DEFAULT_STATUS_INTERVAL", 3600):
        yield


@pytest.fixture
def port() -> int:
    """A free TCP port for this test's listener."""
    return free_port()


@pytest.fixture
def panel() -> FakePanel:
    """An Active 32 Duo with two partitions and an electric fence."""
    return FakePanel()


def make_entry(
    port: int,
    *,
    serials: list[str] | None = None,
    options: dict[str, Any] | None = None,
    subentry_data: dict[str, Any] | None = None,
    title: str | None = None,
) -> MockConfigEntry:
    """Build a config entry with one panel subentry per serial in *serials*.

    The subentry title becomes the device name, and therefore the `entity_id` prefix, so it is set
    to something short and predictable rather than to the serial.
    """
    subentries: list[ConfigSubentryData] = [
        ConfigSubentryData(
            data={CONF_SERIAL: serial, CONF_READ_ONLY: True, **(subentry_data or {})},
            subentry_type=SUBENTRY_TYPE_PANEL,
            title=title or "Active 32 Duo",
            unique_id=serial,
        )
        for serial in (serials if serials is not None else ["0000000001"])
    ]
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"JFL Alarm ({port})",
        data={CONF_HOST: LOOPBACK, CONF_PORT: port},
        options=options or {},
        unique_id=str(port),
        subentries_data=subentries,
    )


def announce_programming(
    coordinator: JflPanelCoordinator, pgms: dict[int, int] | None = None
) -> None:
    """Tell *coordinator* its programming has been read, without driving thirty round trips.

    A real read is the wrong way to do this in a test about what the panel is sent afterwards:
    `serve_programming` consumes the same socket the test then reads its command frames from.

    *pgms* maps PGM number to function byte. A number left out has no record at all, which is what
    a panel whose PGM region did not come back looks like.
    """
    coordinator.programming = replace(
        coordinator.programming,
        read_at=dt_util.utcnow(),
        pgms={
            number: PgmRecord(
                number=number, name="", attributes=bytes([0, 0, 0, 0, 0, function])
            )
            for number, function in (pgms or {}).items()
        },
    )
    coordinator.async_update_listeners()


@pytest.fixture
def entry(port: int) -> MockConfigEntry:
    """A config entry for one Active 32 Duo, with polling effectively switched off.

    The poll interval is pushed out to an hour so that no test depends on a timer firing; the tests
    that care about polling drive it explicitly.
    """
    return make_entry(port)


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> AsyncGenerator[MockConfigEntry]:
    """Add and set up the entry, and make sure it is unloaded afterwards.

    Unloading matters more than usual here: a listener left running holds a port, and the next test
    that asked for "a free port" may have been handed the same one.
    """
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    yield entry
    if entry.state.recoverable:
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def wait_until(
    hass: HomeAssistant, predicate: Callable[[], bool], timeout: float = 5.0
) -> None:
    """Let the event loop run until *predicate* holds.

    Bytes written to a socket do not arrive because `async_block_till_done` was called — they arrive
    when the reader task is scheduled and the kernel has them. Polling a condition is the honest way
    to wait for that; a fixed sleep is either flaky or slow, and usually both.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition was never met")
        await asyncio.sleep(0.01)
        await hass.async_block_till_done()


class PanelConnection:
    """A fake panel's end of a real TCP connection to the listener."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        panel: FakePanel,
    ) -> None:
        """Wrap an open socket to the listener."""
        self.reader = reader
        self.writer = writer
        self.panel = panel
        self._programming_task: asyncio.Task[None] | None = None

    async def send(self, frame: bytes) -> None:
        """Write one frame and let the event loop deliver it."""
        self.writer.write(frame)
        await self.writer.drain()

    async def read_reply(self, timeout: float = 2.0) -> bytes:
        """Read whatever the listener sends back."""
        async with asyncio.timeout(timeout):
            return await self.reader.read(256)

    async def introduce(self, hass: HomeAssistant) -> bytes:
        """Send the connection frame and return the acknowledgement."""
        await self.send(self.panel.connection())
        reply = await self.read_reply()
        await hass.async_block_till_done()
        return reply

    async def report_status(self, hass: HomeAssistant, coordinator) -> None:
        """Send a status frame and wait until the coordinator has actually absorbed it."""
        before = coordinator.data.status
        await self.send(self.panel.status())
        await wait_until(hass, lambda: coordinator.data.status is not before)

    def serve_programming(self) -> None:
        """Answer `0x44` requests in the background, the way a real panel does.

        A programming read is thirty-odd request/reply round trips, and driving those by hand from a
        test would say nothing about the pacing and the correlation that make the read work. So the
        fake panel answers for itself, from the synthetic memory in `FakePanel.programming`.
        """
        if self._programming_task is not None:
            return
        self._programming_task = asyncio.create_task(self._serve_programming())

    async def _serve_programming(self) -> None:
        reader = FrameReader()
        with contextlib.suppress(Exception):
            while True:
                data = await self.reader.read(4096)
                if not data:
                    return
                for frame in reader.feed(data):
                    if frame.cmd == Cmd.READ_PROGRAMMING and len(frame.raw) == 8:
                        address = (frame.raw[4] << 8) | frame.raw[5]
                        await self.send(self.panel.programming(address, frame.raw[6]))
                    elif frame.cmd == Cmd.READ_WIRELESS and len(frame.raw) >= 6:
                        # `0x59` carries [per_page, page] and its reply is correlated by sequence,
                        # so the answer has to echo the sequence byte it was asked with.
                        await self.send(
                            self.panel.wireless_inventory(frame.seq, frame.raw[5])
                        )
                    elif frame.cmd == Cmd.READ_EVENTS and len(frame.raw) == 10:
                        # `0x48` carries [per_page, cursor(4)] and, like `0x59`, is correlated by
                        # sequence: the reply holds records and nothing that identifies the request.
                        cursor = int.from_bytes(frame.raw[5:9], "big")
                        await self.send(self.panel.event_buffer(frame.seq, cursor))

    async def close(self) -> None:
        """Hang up, the way a panel that loses power does."""
        if self._programming_task is not None:
            self._programming_task.cancel()
            self._programming_task = None
        self.writer.close()
        with contextlib.suppress(ConnectionError, OSError):
            await self.writer.wait_closed()


@pytest.fixture
def connect_panel(port: int) -> Generator[Any]:
    """Return a factory that opens a real socket to the listener as a given fake panel."""
    opened: list[PanelConnection] = []

    async def _connect(panel: FakePanel | None = None) -> PanelConnection:
        reader, writer = await asyncio.open_connection(LOOPBACK, port)
        connection = PanelConnection(reader, writer, panel or FakePanel())
        opened.append(connection)
        return connection

    yield _connect

    for connection in opened:
        if connection._programming_task is not None:
            connection._programming_task.cancel()
        connection.writer.close()
