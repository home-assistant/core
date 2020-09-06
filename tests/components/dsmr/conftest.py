"""Common test tools."""
import asyncio

from dsmr_parser.clients.protocol import DSMRProtocol
import pytest

from tests.async_mock import MagicMock, patch


@pytest.fixture
async def dsmr_serial_connection_fixture(hass):
    """Fixture that mocks serial connection."""

    transport = MagicMock(spec=asyncio.Transport)
    protocol = MagicMock(spec=DSMRProtocol)

    async def connection_factory(*args, **kwargs):
        """Return mocked out Asyncio classes."""
        return (transport, protocol)

    connection_factory = MagicMock(wraps=connection_factory)

    with patch(
        "homeassistant.components.dsmr.sensor.create_dsmr_reader", connection_factory
    ):
        yield (connection_factory, transport, protocol)


@pytest.fixture
async def dsmr_tcp_connection_fixture(hass):
    """Fixture that mocks tcp connection."""

    transport = MagicMock(spec=asyncio.Transport)
    protocol = MagicMock(spec=DSMRProtocol)

    async def connection_factory(*args, **kwargs):
        """Return mocked out Asyncio classes."""
        return (transport, protocol)

    connection_factory = MagicMock(wraps=connection_factory)

    with patch(
        "homeassistant.components.dsmr.sensor.create_tcp_dsmr_reader",
        connection_factory,
    ):
        yield (connection_factory, transport, protocol)
