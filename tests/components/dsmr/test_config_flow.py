"""Test the DSMR config flow."""
import asyncio

from dsmr_parser.objects import CosemObject
import pytest

from homeassistant import config_entries
from homeassistant.components.dsmr.const import (
    CONF_DSMR_VERSION,
    CONF_PRECISION,
    CONF_RECONNECT_INTERVAL,
    CONF_SERIAL_ID,
    CONF_SERIAL_ID_GAS,
    DOMAIN,
)
from homeassistant.const import CONF_FORCE_UPDATE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.helpers import entity_registry

import tests.async_mock
from tests.async_mock import Mock, patch

TEST_HOST = "localhost"
TEST_PORT = 1234
TEST_USB_PATH = "/dev/ttyUSB0"
TEST_SERIALNUMBER = "12345678"
TEST_SERIALNUMBER_GAS = "123456789"
TEST_PRECISION = 3
TEST_RECONNECT_INTERVAL = 30
TEST_UNIQUE_ID = f"{DOMAIN}-{TEST_SERIALNUMBER}"
TEST_DSMR_VERSION = "2.2"
TEST_FORCE_UPDATE = False


@pytest.fixture
def mock_connection_factory(monkeypatch):
    """Mock the create functions for serial and TCP Asyncio connections."""
    from dsmr_parser.clients.protocol import DSMRProtocol
    from dsmr_parser.obis_references import (
        EQUIPMENT_IDENTIFIER,
        EQUIPMENT_IDENTIFIER_GAS,
    )

    transport = tests.async_mock.Mock(spec=asyncio.Transport)
    protocol = tests.async_mock.Mock(spec=DSMRProtocol)

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
        EQUIPMENT_IDENTIFIER: CosemObject([{"value": TEST_SERIALNUMBER, "unit": ""}]),
        EQUIPMENT_IDENTIFIER_GAS: CosemObject(
            [{"value": TEST_SERIALNUMBER_GAS, "unit": ""}]
        ),
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


async def test_config_flow_manual_usb_success(hass, mock_connection_factory):
    """
    Test flow manually initialized by user.

    With USB configuration.
    """
    (connection_factory, transport, protocol) = mock_connection_factory

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: "Serial", CONF_DSMR_VERSION: TEST_DSMR_VERSION},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: TEST_USB_PATH}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_options"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PRECISION: TEST_PRECISION,
            CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
            CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_USB_PATH
    assert result["data"] == {
        CONF_HOST: None,
        CONF_PORT: TEST_USB_PATH,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
        CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
    }

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()


async def test_config_flow_manual_host_success(hass, mock_connection_factory):
    """
    Test flow manually initialized by user.

    With Host configuration.
    """
    (connection_factory, transport, protocol) = mock_connection_factory

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: "Host", CONF_DSMR_VERSION: TEST_DSMR_VERSION},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_host"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_options"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PRECISION: TEST_PRECISION,
            CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
            CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == f"{TEST_HOST}:{TEST_PORT}"
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
        CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
    }

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()


async def test_config_flow_manual_usb_connection_error(hass, mock_connection_factory):
    """
    Failed flow manually initialized by the user.

    Serial specified and a connection error.
    """
    (connection_factory, transport, protocol) = mock_connection_factory

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: "Serial", CONF_DSMR_VERSION: TEST_DSMR_VERSION},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.dsmr.config_flow.DSMRConnection.validate_connect",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PORT: TEST_USB_PATH}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_manual_host_connection_error(hass, mock_connection_factory):
    """
    Failed flow manually initialized by the user.

    Host specified and a connection error.
    """
    (connection_factory, transport, protocol) = mock_connection_factory

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: "Host", CONF_DSMR_VERSION: TEST_DSMR_VERSION},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_host"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.dsmr.config_flow.DSMRConnection.validate_connect",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_host"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_manual_usb_wrong_telegram(hass, mock_connection_factory):
    """
    Failed flow manually initialized by the user.

    USB specified and wrong telegram data received.
    """
    (connection_factory, transport, protocol) = mock_connection_factory

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: "Serial", CONF_DSMR_VERSION: TEST_DSMR_VERSION},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    protocol.telegram = {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: TEST_USB_PATH}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {"base": "cannot_communicate"}


async def test_config_flow_manual_usb_no_gas(hass, mock_connection_factory):
    """
    Failed flow manually initialized by the user.

    USB specified and only electricity serial is sent
    """
    from dsmr_parser.obis_references import EQUIPMENT_IDENTIFIER

    (connection_factory, transport, protocol) = mock_connection_factory

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE: "Serial", CONF_DSMR_VERSION: TEST_DSMR_VERSION},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    protocol.telegram = {
        EQUIPMENT_IDENTIFIER: CosemObject([{"value": TEST_SERIALNUMBER, "unit": ""}]),
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: TEST_USB_PATH}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_options"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PRECISION: TEST_PRECISION,
            CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
            CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_USB_PATH
    assert result["data"] == {
        CONF_HOST: None,
        CONF_PORT: TEST_USB_PATH,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
        CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: None,
    }

    await hass.async_block_till_done()

    registry = await entity_registry.async_get_registry(hass)
    assert not registry.async_is_registered("sensor.gas_consumption")
    assert not registry.async_is_registered("sensor.hourly_gas_consumption")

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()


async def test_config_flow_import_usb_success(hass, mock_connection_factory):
    """
    Test flow manually initialized by user.

    With USB configuration.
    """
    (connection_factory, transport, protocol) = mock_connection_factory

    data = {
        CONF_PORT: TEST_USB_PATH,
        CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
    )

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_USB_PATH
    assert result["data"] == {
        CONF_HOST: None,
        CONF_PORT: TEST_USB_PATH,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
        CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
    }

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()


async def test_config_flow_import_host_success(hass, mock_connection_factory):
    """
    Test flow manually initialized by user.

    With Host configuration.
    """
    (connection_factory, transport, protocol) = mock_connection_factory

    data = {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
    )

    assert result["type"] == "create_entry"
    assert result["title"] == f"{TEST_HOST}:{TEST_PORT}"
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
        CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
    }

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()
