"""Fixtures for the KEBA charging station tests.

The station is faked on the wire, not inside the library: the transport
records every UDP command the integration sends and answers ``report N``
requests with the datagrams from ``fixtures/p30.json``. Assertions are made on
what Home Assistant exposes and on the exact command strings, so they do not
depend on how ``keba-kecontact`` is built internally.

The report corpus is synthetic, shaped after the KEBA UDP programmer's guide,
and not captured from hardware.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from keba_kecontact.keba_protocol import KebaProtocol
import pytest

from homeassistant.components.keba.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import load_json_object_fixture

HOST = "192.0.2.10"
UDP_PORT = 7090


class FakeKebaStation:
    """A KEBA charging station on the far side of a fake UDP transport."""

    def __init__(self, reports: dict[str, dict[str, Any]]) -> None:
        """Initialize the station with the reports it answers with."""
        self.reports = reports
        self.sent: list[str] = []
        self.silent = False
        self.local_addr: tuple[str, int] | None = None
        self.remote_addr: tuple[str, int] | None = None
        self.closed = False
        self._protocol: asyncio.DatagramProtocol | None = None

    @property
    def commands(self) -> list[str]:
        """Return the commands sent so far, without report requests."""
        return [cmd for cmd in self.sent if not cmd.startswith("report ")]

    async def create_datagram_endpoint(
        self,
        protocol_factory: Callable[[], asyncio.DatagramProtocol],
        local_addr: tuple[str, int] | None = None,
        remote_addr: tuple[str, int] | None = None,
        **kwargs: Any,
    ) -> tuple[FakeKebaStation, asyncio.DatagramProtocol]:
        """Stand in for loop.create_datagram_endpoint."""
        self.local_addr = local_addr
        self.remote_addr = remote_addr
        self._protocol = protocol_factory()
        self._protocol.connection_made(self)  # type: ignore[arg-type]
        return self, self._protocol

    def sendto(self, data: bytes, addr: tuple[str, int] | None = None) -> None:
        """Record a datagram and answer it like the station would."""
        command = data.decode("cp437")
        self.sent.append(command)
        if self.silent:
            return
        if command.startswith("report "):
            report = self.reports.get(command.removeprefix("report "))
            if report is None:
                return
            reply = json.dumps(report).encode()
        else:
            reply = b"TCH-OK :done\n"
        asyncio.get_running_loop().call_soon(
            self._protocol.datagram_received,  # type: ignore[union-attr]
            reply,
            (HOST, UDP_PORT),
        )

    def push(self, report_id: str, **changes: Any) -> None:
        """Change a report; the next poll picks it up."""
        self.reports[report_id] = {**self.reports[report_id], **changes}

    def close(self) -> None:
        """Close the fake transport."""
        self.closed = True


class PollClock:
    """Stand in for the integration's asyncio.sleep in its polling loop.

    Each sleep is recorded and blocks until the test calls tick(), so the
    polling cadence (normal interval, fast polling after commands) can be
    asserted step by step.
    """

    def __init__(self) -> None:
        """Initialize the clock."""
        self.delays: list[float] = []
        self._waiters: list[asyncio.Future[None]] = []
        self._slept = asyncio.Event()

    async def sleep(self, delay: float) -> None:
        """Record the delay and wait until released."""
        self.delays.append(delay)
        waiter = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        self._slept.set()
        try:
            await waiter
        finally:
            if waiter in self._waiters:
                self._waiters.remove(waiter)

    async def wait_for_sleep(self) -> None:
        """Wait until the polling loop is sleeping again."""
        await asyncio.wait_for(self._slept.wait(), timeout=1)
        self._slept.clear()

    async def tick(self) -> None:
        """End the current sleep and wait for the next poll to finish."""
        self._slept.clear()
        self._waiters[0].set_result(None)
        await self.wait_for_sleep()


async def _yield(delay: float, result: Any = None) -> Any:
    """Replace the library's fixed waits with a single loop iteration."""
    await asyncio.sleep(0)
    return result


@pytest.fixture
def reports() -> dict[str, dict[str, Any]]:
    """Return the report corpus the fake station answers with."""
    return load_json_object_fixture("p30.json", DOMAIN)  # type: ignore[return-value]


@pytest.fixture
def station(
    hass: HomeAssistant, reports: dict[str, dict[str, Any]]
) -> Generator[FakeKebaStation]:
    """Return a fake station wired into the event loop and the library."""
    fake = FakeKebaStation(reports)
    with (
        patch.object(
            hass.loop, "create_datagram_endpoint", fake.create_datagram_endpoint
        ),
        # The library keeps received data in a class attribute, shared by
        # every connection in the process. Give each test its own.
        patch.object(KebaProtocol, "data", {}),
        patch(
            "keba_kecontact.connection.asyncio",
            SimpleNamespace(sleep=_yield, get_event_loop=asyncio.get_event_loop),
        ),
    ):
        yield fake


@pytest.fixture
def poll_clock() -> Generator[PollClock]:
    """Return the clock driving the integration's polling loop."""
    clock = PollClock()
    with patch(
        "homeassistant.components.keba.asyncio", SimpleNamespace(sleep=clock.sleep)
    ):
        yield clock


@pytest.fixture
def keba_config() -> dict[str, Any]:
    """Return the YAML configuration for the integration."""
    return {DOMAIN: {"host": HOST}}


@pytest.fixture
async def setup_keba(
    hass: HomeAssistant,
    station: FakeKebaStation,
    poll_clock: PollClock,
    keba_config: dict[str, Any],
) -> AsyncGenerator[FakeKebaStation]:
    """Set up the integration against the fake station.

    The integration has no unload: its polling task runs until Home Assistant
    stops. Cancel it here so the test leaves no lingering task.
    """
    assert await async_setup_component(hass, DOMAIN, keba_config)
    await hass.async_block_till_done()
    await poll_clock.wait_for_sleep()
    yield station
    await stop_polling(hass)


async def stop_polling(hass: HomeAssistant) -> None:
    """Cancel the integration's polling task, if it is running."""
    keba = hass.data.get(DOMAIN)
    task = getattr(keba, "_polling_task", None)
    if task is None:
        return
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
