"""Common fixtures for the IOmeter tests."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from iometer import Reading, Status
import pytest

from homeassistant.components.iometer.const import DOMAIN
from homeassistant.const import CONF_HOST

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
    reading_queue: asyncio.Queue[Reading],
    status_queue: asyncio.Queue[Status],
) -> Generator[MagicMock]:
    """Mock a IOmeter SSE client."""

    async def watch_readings():
        while True:
            yield await reading_queue.get()

    async def watch_status():
        while True:
            yield await status_queue.get()

    with patch(
        "homeassistant.components.iometer.IOmeterSSEClient",
        autospec=True,
    ) as mock_class:
        client = mock_class.return_value
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.watch_readings.side_effect = watch_readings
        client.watch_status.side_effect = watch_status
        with patch(
            "homeassistant.components.iometer.config_flow.IOmeterSSEClient",
            new=mock_class,
        ):
            yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a IOmeter config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="IOmeter-1ISK0000000000",
        data={CONF_HOST: "10.0.0.2"},
        unique_id="658c2b34-2017-45f2-a12b-731235f8bb97",
        entry_id="01JQ6G5395176MAAWKAAPEZHV6",
    )
