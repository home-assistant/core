"""Tests for the Flashforge config flow."""

from unittest.mock import MagicMock

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.flashforge.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SOURCE
from homeassistant.core import HomeAssistant

from . import get_schema_default, get_schema_suggested, init_integration


async def test_user_flow(hass: HomeAssistant, mock_printer_network: MagicMock):
    """Test the manual user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert not result["errors"]
    schema = result["data_schema"].schema
    assert get_schema_default(schema, CONF_PORT) == 8899

    # Create the config entry and setup device.
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


async def test_user_flow_auto_discover(
    hass: HomeAssistant,
    mock_printer_network: MagicMock,
    mock_printer_discovery: MagicMock,
):
    """Test the auto discovery in manual user flow."""

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


async def test_auto_discover_no_devices(
    hass: HomeAssistant,
    mock_printer_network: MagicMock,
    mock_printer_discovery: MagicMock,
):
    """Test the auto discovery didn't find any devices."""
    mock_printer_discovery.return_value = []

    # User leaved empty form fields to trigger auto discover.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data={},
    )

    # Assert that no devices discovered.
    assert result["reason"] == "no_devices_found"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_auto_discover_device_error(
    hass: HomeAssistant,
    mock_printer_network: MagicMock,
    mock_printer_discovery: MagicMock,
):
    """Test the auto discovery found a device that's not responing as expected."""
    mock_printer_network.connect.side_effect = TimeoutError("timeout")

    # User leaved empty form fields to trigger auto discover.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: config_entries.SOURCE_USER},
        data={},
    )

    # Assert that no devices discovered.
    assert result["reason"] == "no_devices_found"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_connection_timeout(hass: HomeAssistant, mock_printer_network: MagicMock):
    """Test what happens if there is a connection timeout."""
    mock_printer_network.connect.side_effect = TimeoutError("timeout")

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


async def test_connection_error(hass: HomeAssistant, mock_printer_network: MagicMock):
    """Test what happens if there is a connection Error."""
    mock_printer_network.connect.side_effect = ConnectionError("conn_error")

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


async def test_user_device_exists_abort(
    hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test if device is already configured."""
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


async def test_unload_integration(hass: HomeAssistant, mock_printer_network: MagicMock):
    """Test of unload integration."""
    entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_printer_not_responding(
    hass: HomeAssistant, mock_printer_network: MagicMock
):
    """Test if printer not responding during setup."""
    mock_printer_network.connect.side_effect = ConnectionError("conn_error")
    entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.SETUP_RETRY

    mock_printer_network.connect.side_effect = TimeoutError("timeout")
    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
