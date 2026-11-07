"""Fixtures for the KEBA charging station tests.

The keba-kecontact library is mocked. ``KebaHandler`` subclasses the library's
``KebaKeContact``; its own code (setup checks, polling, fast polling, update
listeners) runs for real, and the library methods it calls are mocks.

``get_value`` reads a dict holding what keba-kecontact 1.3.0 returns for a real
station. The dicts in ``fixtures/`` were made by feeding report datagrams
captured from a KC-P30 (firmware P30 v 3.10.53) through the library's own
parser: ``p30.json`` (the default) is idle with the cable plugged in at the
station only, ``p30_plugged.json`` is plugged into a car but not yet enabled,
and ``p30_charging.json`` is charging. The serial is replaced with
``12345678`` and the RFID fields with zeros.

The integration's polling loop sleeps with ``asyncio.sleep``; tests move time
forward with ``freezer`` and ``async_fire_time_changed``.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from keba_kecontact.connection import KebaKeContact
import pytest
from pytest_homeassistant.common import (
    async_fire_time_changed,
    load_json_object_fixture,
)

from homeassistant.components.keba.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

HOST = "192.0.2.10"
POLL_INTERVAL = 5  # seconds; the default, and the minimum refresh_interval
LIBRARY_COMMANDS = (
    "set_failsafe",
    "set_energy",
    "set_current",
    "set_text",
    "start",
    "stop",
    "enable",
)


@pytest.fixture
def corpus() -> str:
    """Return the fixture file with the station's data."""
    return "p30.json"


@pytest.fixture
def keba_data(corpus: str) -> dict[str, Any]:
    """Return the data the library reports for the station."""
    return load_json_object_fixture(corpus, DOMAIN)


@pytest.fixture
def mock_keba(
    hass: HomeAssistant, keba_data: dict[str, Any], freezer: FrozenDateTimeFactory
) -> Generator[MagicMock]:
    """Mock the keba-kecontact library under the integration.

    ``request_data`` does what the library does once the reports arrive: it
    hands its data to the callback the integration registered.

    Depends on ``freezer`` so that time is frozen before the polling loop
    schedules its first sleep.
    """
    client = MagicMock()
    client.setup = AsyncMock()
    client.request_data = AsyncMock(
        side_effect=lambda: hass.data[DOMAIN].callback(keba_data)
    )
    client.get_value = MagicMock(side_effect=keba_data.get)
    for command in LIBRARY_COMMANDS:
        setattr(client, command, AsyncMock())
    with patch.multiple(
        KebaKeContact,
        setup=client.setup,
        request_data=client.request_data,
        get_value=client.get_value,
        **{command: getattr(client, command) for command in LIBRARY_COMMANDS},
    ):
        yield client


@pytest.fixture
def keba_config() -> dict[str, Any]:
    """Return the YAML configuration for the integration."""
    return {DOMAIN: {"host": HOST}}


@pytest.fixture
async def setup_keba(
    hass: HomeAssistant,
    mock_keba: MagicMock,
    keba_config: dict[str, Any],
) -> AsyncGenerator[MagicMock]:
    """Set up the integration against the mocked library.

    The integration has no unload: its polling task runs until Home Assistant
    stops. Cancel it here so the test leaves no lingering task.
    """
    assert await async_setup_component(hass, DOMAIN, keba_config)
    await async_settle(hass)
    yield mock_keba
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
    mock_keba: MagicMock,
    limit: int = 60,
) -> int:
    """Move time forward a second at a time until the station is polled.

    Return how many seconds that took. ``async_fire_time_changed`` runs
    timers up to half a second early, so whole-second steps land on each
    delay exactly.
    """
    polls_before = mock_keba.request_data.await_count
    for seconds in range(1, limit + 1):
        await async_advance(hass, freezer, 1)
        if mock_keba.request_data.await_count > polls_before:
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
