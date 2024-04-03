"""Common test tools."""

import asyncio
from unittest.mock import MagicMock, patch

from dsmr_parser.clients.protocol import DSMRProtocol
from dsmr_parser.clients.rfxtrx_protocol import RFXtrxDSMRProtocol
from dsmr_parser.obis_references import (
    BELGIUM_EQUIPMENT_IDENTIFIER,
    EQUIPMENT_IDENTIFIER,
    EQUIPMENT_IDENTIFIER_GAS,
    LUXEMBOURG_EQUIPMENT_IDENTIFIER,
    P1_MESSAGE_TIMESTAMP,
    Q3D_EQUIPMENT_IDENTIFIER,
)
from dsmr_parser.objects import CosemObject
import pytest


@pytest.fixture
async def dsmr_connection_fixture(hass):
    """Fixture that mocks serial connection."""

    transport = MagicMock(spec=asyncio.Transport)
    protocol = MagicMock(spec=DSMRProtocol)

    async def connection_factory(*args, **kwargs):
        """Return mocked out Asyncio classes."""
        return (transport, protocol)

    connection_factory = MagicMock(wraps=connection_factory)

    with (
        patch(
            "homeassistant.components.dsmr.sensor.create_dsmr_reader",
            connection_factory,
        ),
        patch(
            "homeassistant.components.dsmr.sensor.create_tcp_dsmr_reader",
            connection_factory,
        ),
    ):
        yield (connection_factory, transport, protocol)


@pytest.fixture
async def rfxtrx_dsmr_connection_fixture(hass):
    """Fixture that mocks RFXtrx connection."""

    transport = MagicMock(spec=asyncio.Transport)
    protocol = MagicMock(spec=RFXtrxDSMRProtocol)

    async def connection_factory(*args, **kwargs):
        """Return mocked out Asyncio classes."""
        return (transport, protocol)

    connection_factory = MagicMock(wraps=connection_factory)

    with (
        patch(
            "homeassistant.components.dsmr.sensor.create_rfxtrx_dsmr_reader",
            connection_factory,
        ),
        patch(
            "homeassistant.components.dsmr.sensor.create_rfxtrx_tcp_dsmr_reader",
            connection_factory,
        ),
    ):
        yield (connection_factory, transport, protocol)


@pytest.fixture
async def dsmr_connection_send_validate_fixture(hass):
    """Fixture that mocks serial connection."""

    transport = MagicMock(spec=asyncio.Transport)
    protocol = MagicMock(spec=DSMRProtocol)

    protocol.telegram = {
        EQUIPMENT_IDENTIFIER: CosemObject(
            EQUIPMENT_IDENTIFIER, [{"value": "12345678", "unit": ""}]
        ),
        EQUIPMENT_IDENTIFIER_GAS: CosemObject(
            EQUIPMENT_IDENTIFIER_GAS, [{"value": "123456789", "unit": ""}]
        ),
        P1_MESSAGE_TIMESTAMP: CosemObject(
            P1_MESSAGE_TIMESTAMP, [{"value": "12345678", "unit": ""}]
        ),
    }

    async def connection_factory(*args, **kwargs):
        """Return mocked out Asyncio classes."""
        if args[1] == "5B":
            protocol.telegram = {
                BELGIUM_EQUIPMENT_IDENTIFIER: CosemObject(
                    BELGIUM_EQUIPMENT_IDENTIFIER, [{"value": "12345678", "unit": ""}]
                ),
                EQUIPMENT_IDENTIFIER_GAS: CosemObject(
                    EQUIPMENT_IDENTIFIER_GAS, [{"value": "123456789", "unit": ""}]
                ),
            }
        if args[1] == "5L":
            protocol.telegram = {
                LUXEMBOURG_EQUIPMENT_IDENTIFIER: CosemObject(
                    LUXEMBOURG_EQUIPMENT_IDENTIFIER, [{"value": "12345678", "unit": ""}]
                ),
                EQUIPMENT_IDENTIFIER_GAS: CosemObject(
                    EQUIPMENT_IDENTIFIER_GAS, [{"value": "123456789", "unit": ""}]
                ),
            }
        if args[1] == "5S":
            protocol.telegram = {
                P1_MESSAGE_TIMESTAMP: CosemObject(
                    P1_MESSAGE_TIMESTAMP, [{"value": "12345678", "unit": ""}]
                ),
            }
        if args[1] == "Q3D":
            protocol.telegram = {
                Q3D_EQUIPMENT_IDENTIFIER: CosemObject(
                    Q3D_EQUIPMENT_IDENTIFIER, [{"value": "12345678", "unit": ""}]
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

    with (
        patch(
            "homeassistant.components.dsmr.config_flow.create_dsmr_reader",
            connection_factory,
        ),
        patch(
            "homeassistant.components.dsmr.config_flow.create_tcp_dsmr_reader",
            connection_factory,
        ),
    ):
        yield (connection_factory, transport, protocol)


@pytest.fixture
async def rfxtrx_dsmr_connection_send_validate_fixture(hass):
    """Fixture that mocks serial connection."""

    transport = MagicMock(spec=asyncio.Transport)
    protocol = MagicMock(spec=RFXtrxDSMRProtocol)

    protocol.telegram = {
        EQUIPMENT_IDENTIFIER: CosemObject(
            EQUIPMENT_IDENTIFIER, [{"value": "12345678", "unit": ""}]
        ),
        EQUIPMENT_IDENTIFIER_GAS: CosemObject(
            EQUIPMENT_IDENTIFIER_GAS, [{"value": "123456789", "unit": ""}]
        ),
        P1_MESSAGE_TIMESTAMP: CosemObject(
            P1_MESSAGE_TIMESTAMP, [{"value": "12345678", "unit": ""}]
        ),
    }

    async def connection_factory(*args, **kwargs):
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

    with (
        patch(
            "homeassistant.components.dsmr.config_flow.create_rfxtrx_dsmr_reader",
            connection_factory,
        ),
        patch(
            "homeassistant.components.dsmr.config_flow.create_rfxtrx_tcp_dsmr_reader",
            connection_factory,
        ),
    ):
        yield (connection_factory, transport, protocol)
