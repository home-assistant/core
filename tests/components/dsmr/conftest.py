"""Common test tools."""
import asyncio

from dsmr_parser.clients.protocol import DSMRProtocol
from dsmr_parser.obis_references import (
    EQUIPMENT_IDENTIFIER,
    EQUIPMENT_IDENTIFIER_GAS,
    LUXEMBOURG_EQUIPMENT_IDENTIFIER,
)
from dsmr_parser.objects import CosemObject
import pytest

from tests.async_mock import MagicMock, patch


@pytest.fixture
async def dsmr_connection_fixture(hass):
    """Fixture that mocks serial connection."""

    transport = MagicMock(spec=asyncio.Transport)
    protocol = MagicMock(spec=DSMRProtocol)

    async def connection_factory(*args, **kwargs):
        """Return mocked out Asyncio classes."""
        return (transport, protocol)

    connection_factory = MagicMock(wraps=connection_factory)

    with patch(
        "homeassistant.components.dsmr.sensor.create_dsmr_reader", connection_factory
    ), patch(
        "homeassistant.components.dsmr.sensor.create_tcp_dsmr_reader",
        connection_factory,
    ):
        yield (connection_factory, transport, protocol)


@pytest.fixture
async def dsmr_connection_send_validate_fixture(hass):
    """Fixture that mocks serial connection."""

    transport = MagicMock(spec=asyncio.Transport)
    protocol = MagicMock(spec=DSMRProtocol)

    protocol.telegram = {
        EQUIPMENT_IDENTIFIER: CosemObject([{"value": "12345678", "unit": ""}]),
        EQUIPMENT_IDENTIFIER_GAS: CosemObject([{"value": "123456789", "unit": ""}]),
    }

    async def connection_factory(*args, **kwargs):
        """Return mocked out Asyncio classes."""
        if args[1] == "5L":
            protocol.telegram = {
                LUXEMBOURG_EQUIPMENT_IDENTIFIER: CosemObject(
                    [{"value": "12345678", "unit": ""}]
                ),
                EQUIPMENT_IDENTIFIER_GAS: CosemObject(
                    [{"value": "123456789", "unit": ""}]
                ),
            }

        return (transport, protocol)

    connection_factory = MagicMock(wraps=connection_factory)

    async def wait_closed():
        if isinstance(connection_factory.call_args_list[0][0][2], str):
            # TCP
            telegram_callback = connection_factory.call_args_list[0][0][3]
        else:
            # Serial
            telegram_callback = connection_factory.call_args_list[0][0][2]

        telegram_callback(protocol.telegram)

    protocol.wait_closed = wait_closed

    with patch(
        "homeassistant.components.dsmr.config_flow.create_dsmr_reader",
        connection_factory,
    ), patch(
        "homeassistant.components.dsmr.config_flow.create_tcp_dsmr_reader",
        connection_factory,
    ):
        yield (connection_factory, transport, protocol)
