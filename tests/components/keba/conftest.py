"""Fixtures for the KEBA charging station tests.

The station is faked on the wire, not inside the library: the transport
records every UDP command the integration sends and answers ``report N``
requests with the datagrams from a report corpus in ``fixtures/``. Assertions are made on
what Home Assistant exposes and on the exact command strings, so they do not
depend on how ``keba-kecontact`` is built internally.

The corpora hold raw datagrams captured from a KC-P30 (firmware
P30 v 3.10.53). ``p30.json`` (the default) is idle with the cable plugged in at
the station only, ``p30_plugged.json`` is plugged into a car but not yet
enabled, and ``p30_charging.json`` is charging. The serial is replaced with
``12345678`` and the RFID fields with zeros; everything else, whitespace
included, is as received. A report a test has not changed is answered byte for
byte.

The integration's polling loop sleeps with ``asyncio.sleep``; tests move time
forward with ``freezer`` and ``async_fire_time_changed``.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
from datetime import timedelta
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from keba_kecontact.keba_protocol import KebaProtocol
import pytest
from pytest_homeassistant.common import (
    async_fire_time_changed,
    load_json_object_fixture,
)

from homeassistant.components.keba.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

HOST = "192.0.2.10"
UDP_PORT = 7090
POLL_INTERVAL = 5  # seconds; the default, and the minimum refresh_interval


class FakeKebaStation:
    """A KEBA charging station on the far side of a fake UDP transport.

    Replies are delivered at once, from inside ``sendto``.
    """

    def __init__(self, raw_reports: dict[str, str]) -> None:
        """Initialize the station with the raw datagrams it answers with."""
        self.raw_reports = raw_reports
        self.reports: dict[str, dict[str, Any]] = {
            key: json.loads(raw) for key, raw in raw_reports.items()
        }
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
            report_id = command.removeprefix("report ")
            report = self.reports.get(report_id)
            if report is None:
                return
            raw = self.raw_reports.get(report_id)
            if raw is not None and json.loads(raw) == report:
                reply = raw.encode()
            else:
                reply = json.dumps(report).encode()
        else:
            reply = b"TCH-OK :done\n"
        self.broadcast(reply)

    def broadcast(self, data: bytes) -> None:
        """Send a datagram to the integration, asked for or not."""
        self._protocol.datagram_received(data, (HOST, UDP_PORT))  # type: ignore[union-attr]

    def push(self, report_id: str, **changes: Any) -> None:
        """Change a report; the next poll picks it up."""
        self.reports[report_id] = {**self.reports[report_id], **changes}

    def close(self) -> None:
        """Close the fake transport."""
        self.closed = True


@pytest.fixture
def corpus() -> str:
    """Return the fixture file of the report corpus."""
    return "p30.json"


@pytest.fixture
def raw_reports(corpus: str) -> dict[str, str]:
    """Return the raw report datagrams the fake station answers with."""
    return load_json_object_fixture(corpus, DOMAIN)  # type: ignore[return-value]


@pytest.fixture
def station(
    raw_reports: dict[str, str], freezer: FrozenDateTimeFactory
) -> Generator[FakeKebaStation]:
    """Return a fake station wired into the library.

    keba-kecontact 1.3.0 opens its datagram endpoint on
    ``asyncio.get_event_loop()``, and waits with ``asyncio.sleep`` between
    requests and for the first reply. Its ``asyncio`` is swapped for one that
    hands it the fake station and does not wait.

    Depends on ``freezer`` so that time is frozen before the polling loop
    schedules its first sleep.
    """
    fake = FakeKebaStation(raw_reports)
    with (
        # The library keeps received data in a class attribute, shared by
        # every connection in the process. Give each test its own.
        patch.object(KebaProtocol, "data", {}),
        patch(
            "keba_kecontact.connection.asyncio",
            SimpleNamespace(sleep=AsyncMock(), get_event_loop=lambda: fake),
        ),
    ):
        yield fake


@pytest.fixture
def keba_config() -> dict[str, Any]:
    """Return the YAML configuration for the integration."""
    return {DOMAIN: {"host": HOST}}


@pytest.fixture
async def setup_keba(
    hass: HomeAssistant,
    station: FakeKebaStation,
    keba_config: dict[str, Any],
) -> AsyncGenerator[FakeKebaStation]:
    """Set up the integration against the fake station.

    The integration has no unload: its polling task runs until Home Assistant
    stops. Cancel it here so the test leaves no lingering task.
    """
    assert await async_setup_component(hass, DOMAIN, keba_config)
    await async_settle(hass)
    yield station
    await stop_polling(hass)


async def async_settle(hass: HomeAssistant) -> None:
    """Wait until the polling loop has finished its current poll.

    The loop reschedules itself in a task created with ``loop.create_task``.
    ``async_block_till_done`` does not track those, and returns one loop
    iteration before the new task has polled.
    """
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def async_advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Move time forward and run the polls that fall due."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await async_settle(hass)


async def async_seconds_until_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    station: FakeKebaStation,
    limit: int = 60,
) -> int:
    """Move time forward a second at a time until the station is polled.

    Return how many seconds that took. ``async_fire_time_changed`` runs
    timers up to half a second early, so whole-second steps land on each
    delay exactly.
    """
    sent_before = len(station.sent)
    for seconds in range(1, limit + 1):
        await async_advance(hass, freezer, 1)
        if station.sent[sent_before:]:
            return seconds
    pytest.fail(f"No poll within {limit} seconds")


async def stop_polling(hass: HomeAssistant) -> None:
    """Cancel the integration's polling task, if it is running."""
    keba = hass.data.get(DOMAIN)
    task = getattr(keba, "_polling_task", None)
    if task is None:
        return
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
