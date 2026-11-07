"""Fixtures for local storage integration tests."""

import asyncio
from collections.abc import AsyncIterator, Generator
from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from aioelecway import StorageData, Telemetry
import pytest

from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

SERIAL = "ES25082799999"
MODEL = "S3-20-EW02-08"
DATA = StorageData(
    SERIAL,
    MODEL,
    Telemetry(797.3, 803, -3.2, 99, 0.74, 1.72, 0.07, 1.05, 0.06, 0.06),
)


@pytest.fixture(autouse=True)
def mock_zeroconf_setup() -> Generator[AsyncMock]:
    """Keep HA dependency setup from opening multicast sockets in unit tests."""
    with patch(
        "homeassistant.components.zeroconf.async_setup", return_value=True
    ) as mock:
        yield mock


@pytest.fixture
def discovery() -> ZeroconfServiceInfo:
    """A storage announcement using a nondefault port."""
    return ZeroconfServiceInfo(
        ip_address=ip_address("192.0.2.10"),
        ip_addresses=[ip_address("192.0.2.10")],
        port=8080,
        hostname="storage.local.",
        type="_http._tcp.local.",
        name=f"EwayEnergyStorage-{SERIAL}._http._tcp.local.",
        properties={},
    )


@pytest.fixture
def mock_discover(discovery: ZeroconfServiceInfo) -> Generator[AsyncMock]:
    """Return one unconfigured device."""
    with patch(
        "homeassistant.components.elecway.config_flow.async_discover",
        return_value={SERIAL: discovery},
    ) as mock:
        yield mock


@pytest.fixture
def updates() -> asyncio.Queue[StorageData | None]:
    """Queue library events to exercise availability and recovery."""
    return asyncio.Queue()


@pytest.fixture
def mock_client(updates: asyncio.Queue[StorageData | None]) -> Generator[AsyncMock]:
    """Mock the external library while retaining its cancellation contract."""
    with (
        patch(
            "homeassistant.components.elecway.StorageClient", autospec=True
        ) as factory,
        patch(
            "homeassistant.components.elecway.config_flow.StorageClient", new=factory
        ),
    ):
        client = factory.return_value
        client.connect.return_value = DATA

        async def stream() -> AsyncIterator[StorageData | None]:
            try:
                while True:
                    yield await updates.get()
            finally:
                await client.disconnect()

        client.updates.side_effect = stream
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Isolate configuration flow tests from entity setup."""
    with patch(
        "homeassistant.components.elecway.async_setup_entry", return_value=True
    ) as mock:
        yield mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Provide one native storage entry."""
    return MockConfigEntry(
        domain="elecway",
        title=f"Elecway {SERIAL}",
        unique_id=SERIAL,
        data={CONF_HOST: "192.0.2.10", CONF_PORT: 8080, CONF_MODEL: MODEL},
    )
