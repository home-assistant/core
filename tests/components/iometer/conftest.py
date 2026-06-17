"""Common fixtures for the IOmeter tests."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from iometer import Reading, Status
import pytest

from homeassistant.components.iometer.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.iometer.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def reading_queue() -> asyncio.Queue[Reading]:
    """Queue for injecting readings into the SSE stream during tests."""
    q: asyncio.Queue[Reading] = asyncio.Queue()
    q.put_nowait(Reading.from_json(load_fixture("reading.json", DOMAIN)))
    return q


@pytest.fixture
def status_queue() -> asyncio.Queue[Status]:
    """Queue for injecting statuses into the SSE stream during tests."""
    q: asyncio.Queue[Status] = asyncio.Queue()
    q.put_nowait(Status.from_json(load_fixture("status.json", DOMAIN)))
    return q


@pytest.fixture
def mock_iometer_client(
    hass: HomeAssistant,
    reading_queue: asyncio.Queue[Reading],
    status_queue: asyncio.Queue[Status],
) -> Generator[MagicMock]:
    """Mock an IOmeter SSE client."""

    def subscribe_readings(on_reading, _on_error=None):
        async def _feed():
            while True:
                reading = await reading_queue.get()
                on_reading(reading)

        task = hass.async_create_background_task(_feed(), "mock_reading_feed")
        return task.cancel

    def subscribe_status(on_status, _on_error=None):
        async def _feed():
            while True:
                status = await status_queue.get()
                on_status(status)

        task = hass.async_create_background_task(_feed(), "mock_status_feed")
        return task.cancel

    async def watch_status():
        while True:
            yield await status_queue.get()

    with patch(
        "homeassistant.components.iometer.IOmeterSSEClient",
    ) as mock_class:
        client = mock_class.return_value
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.subscribe_readings.side_effect = subscribe_readings
        client.subscribe_status.side_effect = subscribe_status
        with patch(
            "homeassistant.components.iometer.config_flow.IOmeterSSEClient",
            new=mock_class,
        ):
            client.watch_status.side_effect = watch_status
            yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock an IOmeter config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="IOmeter-1ISK0000000000",
        data={CONF_HOST: "10.0.0.2"},
        unique_id="658c2b34-2017-45f2-a12b-731235f8bb97",
        entry_id="01JQ6G5395176MAAWKAAPEZHV6",
    )
