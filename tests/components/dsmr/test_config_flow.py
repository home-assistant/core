"""Test the DSMR config flow."""
import asyncio
from itertools import chain, repeat

from dsmr_parser.clients.protocol import DSMRProtocol
from dsmr_parser.obis_references import EQUIPMENT_IDENTIFIER, EQUIPMENT_IDENTIFIER_GAS
from dsmr_parser.objects import CosemObject
import pytest
import serial

from homeassistant import config_entries, setup
from homeassistant.components.dsmr import DOMAIN

from tests.async_mock import DEFAULT, AsyncMock, Mock, patch
from tests.common import MockConfigEntry

SERIAL_DATA = {"serial_id": "12345678", "serial_id_gas": "123456789"}


@pytest.fixture
def mock_connection_factory(monkeypatch):
    """Mock the create functions for serial and TCP Asyncio connections."""
    transport = Mock(spec=asyncio.Transport)
    protocol = Mock(spec=DSMRProtocol)

    async def connection_factory(*args, **kwargs):
        """Return mocked out Asyncio classes."""
        return (transport, protocol)

    connection_factory = Mock(wraps=connection_factory)

    # apply the mock to both connection factories
    monkeypatch.setattr(
        "homeassistant.components.dsmr.config_flow.create_dsmr_reader",
        connection_factory,
    )
    monkeypatch.setattr(
        "homeassistant.components.dsmr.config_flow.create_tcp_dsmr_reader",
        connection_factory,
    )

    protocol.telegram = {
        EQUIPMENT_IDENTIFIER: CosemObject([{"value": "12345678", "unit": ""}]),
        EQUIPMENT_IDENTIFIER_GAS: CosemObject([{"value": "123456789", "unit": ""}]),
    }

    async def wait_closed():
        if isinstance(connection_factory.call_args_list[0][0][2], str):
            # TCP
            telegram_callback = connection_factory.call_args_list[0][0][3]
        else:
            # Serial
            telegram_callback = connection_factory.call_args_list[0][0][2]

        telegram_callback(protocol.telegram)

    protocol.wait_closed = wait_closed

    return connection_factory, transport, protocol


async def test_import_usb(hass, mock_connection_factory):
    """Test we can import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
    }

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_data,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "/dev/ttyUSB0"
    assert result["data"] == {**entry_data, **SERIAL_DATA}


async def test_import_usb_failed_connection(hass, monkeypatch, mock_connection_factory):
    """Test we can import."""
    (connection_factory, transport, protocol) = mock_connection_factory

    await setup.async_setup_component(hass, "persistent_notification", {})

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
    }

    # override the mock to have it fail the first time and succeed after
    first_fail_connection_factory = AsyncMock(
        return_value=(transport, protocol),
        side_effect=chain([serial.serialutil.SerialException], repeat(DEFAULT)),
    )

    monkeypatch.setattr(
        "homeassistant.components.dsmr.config_flow.create_dsmr_reader",
        first_fail_connection_factory,
    )

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_data,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_import_usb_no_data(hass, monkeypatch, mock_connection_factory):
    """Test we can import."""
    (connection_factory, transport, protocol) = mock_connection_factory

    await setup.async_setup_component(hass, "persistent_notification", {})

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
    }

    # override the mock to have it fail the first time and succeed after
    wait_closed = AsyncMock(
        return_value=(transport, protocol),
        side_effect=chain([asyncio.TimeoutError], repeat(DEFAULT)),
    )

    protocol.wait_closed = wait_closed

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_data,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_communicate"


async def test_import_usb_wrong_telegram(hass, mock_connection_factory):
    """Test we can import."""
    (connection_factory, transport, protocol) = mock_connection_factory

    await setup.async_setup_component(hass, "persistent_notification", {})

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
    }

    protocol.telegram = {}

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_data,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_communicate"


async def test_import_network(hass, mock_connection_factory):
    """Test we can import from network."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry_data = {
        "host": "localhost",
        "port": "1234",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
    }

    with patch("homeassistant.components.dsmr.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_data,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "localhost:1234"
    assert result["data"] == {**entry_data, **SERIAL_DATA}


async def test_import_update(hass, mock_connection_factory):
    """Test we can import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=entry_data,
        unique_id="/dev/ttyUSB0",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dsmr.async_setup_entry", return_value=True
    ), patch("homeassistant.components.dsmr.async_unload_entry", return_value=True):
        await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    new_entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 3,
        "reconnect_interval": 30,
    }

    with patch(
        "homeassistant.components.dsmr.async_setup_entry", return_value=True
    ), patch("homeassistant.components.dsmr.async_unload_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=new_entry_data,
        )

    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    assert entry.data["precision"] == 3
