"""Tests for the Flashforge config flow."""

from unittest.mock import Mock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.flashforge.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SOURCE
from homeassistant.core import HomeAssistant

from . import (
    get_schema_default,
    get_schema_suggested,
    init_integration,
    prepare_mocked_connection,
)


@patch("ffpp.Discovery.getPrinters", return_value=[])
async def test_user_flow(mock_discovery: Mock, hass: HomeAssistant):
    """Test the manual user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert not result["errors"]
    schema = result["data_schema"].schema
    assert get_schema_default(schema, CONF_PORT) == 8899

    # Create the config entry and setup device.
    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        prepare_mocked_connection(mock_network.return_value)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "127.0.0.1",
                CONF_PORT: 8899,
            },
        )

    assert result["data"][CONF_IP_ADDRESS] == "127.0.0.1"
    assert result["data"][CONF_PORT] == 8899
    assert result["data"][CONF_SERIAL_NUMBER] == "SNADVA1234567"
    assert result["title"] == "Adventurer4"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].unique_id == "SNADVA1234567"


@patch("ffpp.Discovery.getPrinters", return_value=[("Adventurer4", "192.168.0.64")])
async def test_user_flow_auto_discover(mock_discovery: Mock, hass: HomeAssistant):
    """Test the auto discovery in manual user flow."""

    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        prepare_mocked_connection(mock_network.return_value)

        # User leaved empty form fields to trigger auto discover.
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data={},
        )

    # Assert that we found mocked printer.
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["description_placeholders"] == {
        "machine_name": "Adventurer4",
        "ip_addr": "192.168.0.64",
    }
    assert result["step_id"] == "auto_confirm"
    progress = hass.config_entries.flow.async_progress()
    assert len(progress) == 1
    assert progress[0]["flow_id"] == result["flow_id"]
    assert progress[0]["context"]["confirm_only"] is True

    # User confirm to add this device.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    # Assert everything is ok.
    assert result["data"][CONF_IP_ADDRESS] == "192.168.0.64"
    assert result["data"][CONF_PORT] == 8899
    assert result["data"][CONF_SERIAL_NUMBER] == "SNADVA1234567"
    assert result["title"] == "Adventurer4"
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


@patch("ffpp.Discovery.getPrinters", return_value=[])
async def test_auto_discover_no_devices(mock_discovery: Mock, hass: HomeAssistant):
    """Test the auto discovery didn't find any devices."""

    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        prepare_mocked_connection(mock_network.return_value)

        # User leaved empty form fields to trigger auto discover.
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data={},
        )

    # Assert that no devices discovered.
    assert result["reason"] == "no_devices_found"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


@patch("ffpp.Discovery.getPrinters", return_value=[("Adventurer4", "192.168.0.64")])
async def test_auto_discover_device_error(mock_discovery: Mock, hass: HomeAssistant):
    """Test the auto discovery found a device that's not responing as expected."""

    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        printer = mock_network.return_value
        printer.connect.side_effect = TimeoutError("timeout")

        # User leaved empty form fields to trigger auto discover.
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data={},
        )

    # Assert that no devices discovered.
    assert result["reason"] == "no_devices_found"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_connection_timeout(hass: HomeAssistant):
    """Test what happens if there is a connection timeout."""

    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        # prepare_mocked_connection(mock_network.return_value)
        printer = mock_network.return_value
        printer.connect.side_effect = TimeoutError("timeout")

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "127.0.0.1",
                CONF_PORT: 8899,
            },
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_IP_ADDRESS: "cannot_connect"}
    schema = result["data_schema"].schema
    assert get_schema_suggested(schema, CONF_IP_ADDRESS) == "127.0.0.1"
    assert get_schema_default(schema, CONF_PORT) == 8899


async def test_connection_error(hass: HomeAssistant):
    """Test what happens if there is a connection Error."""

    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        # prepare_mocked_connection(mock_network.return_value)
        printer_network = mock_network.return_value
        printer_network.connect.side_effect = ConnectionError("conn_error")

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "127.0.0.1",
                CONF_PORT: 8899,
            },
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_IP_ADDRESS: "cannot_connect"}


async def test_user_device_exists_abort(hass: HomeAssistant):
    """Test if device is already configured."""

    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        prepare_mocked_connection(mock_network.return_value)

        await init_integration(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "127.0.0.1",
                CONF_PORT: 8899,
            },
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_unload_integration(hass: HomeAssistant):
    """Test of unload integration."""

    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        prepare_mocked_connection(mock_network.return_value)

        entry = await init_integration(hass)
        assert entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_printer_not_responding(hass: HomeAssistant):
    """Test if printer not responding during setup."""

    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        printer_network = mock_network.return_value
        printer_network.connect.side_effect = ConnectionError("conn_error")
        # prepare_mocked_connection(mock_network.return_value)

        entry = await init_integration(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY

    with patch("ffpp.Printer.Network", autospec=True) as mock_network:
        printer_network = mock_network.return_value
        printer_network.connect.side_effect = TimeoutError("timeout")
        # prepare_mocked_connection(mock_network.return_value)

        entry = await init_integration(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY
