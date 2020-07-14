"""Define tests for the growatt_rs232 inverter config flow."""

from growattRS232 import ATTR_SERIAL_NUMBER, ModbusException, PortException

from homeassistant import data_entry_flow
from homeassistant.components.growatt_rs232.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_PORT

from .const import CONFIG, CONTEXT_USER, DATA_NORMAL, PATCH, TITLE

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context=CONTEXT_USER)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_create_entry_with_port(hass):
    """Test that the user step works with USB port."""
    with patch(
        PATCH, return_value=DATA_NORMAL,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context=CONTEXT_USER, data=CONFIG
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == TITLE
        assert result["data"][CONF_PORT] == CONFIG[CONF_PORT]
        assert result["data"][CONF_ADDRESS] == CONFIG[CONF_ADDRESS]


async def test_port_exception(hass):
    """Test invalid USB port in user_input."""
    with patch(PATCH, side_effect=PortException("")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context=CONTEXT_USER, data=CONFIG
        )

    assert result["errors"] == {CONF_PORT: "port_error"}


async def test_modbus_exception(hass):
    """Test modbus_exception in user_input."""
    with patch(
        PATCH, side_effect=ModbusException(""),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context=CONTEXT_USER, data=CONFIG
        )

    assert result["errors"] == {CONF_ADDRESS: "modbus_error"}


async def test_connection_error(hass):
    """Test connection to inverter error."""
    with patch(PATCH, side_effect=ConnectionError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context=CONTEXT_USER, data=CONFIG
        )

    assert result["errors"] == {"base": "connection_error"}


async def test_missing_serial_number(hass):
    """Test missing serialnumber."""
    with patch(
        PATCH, return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context=CONTEXT_USER, data=CONFIG
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "serial_number_error"


async def test_device_exists_abort(hass):
    """Test we abort config flow if Growaat inverter already configured."""
    with patch(
        PATCH, return_value=DATA_NORMAL,
    ):
        MockConfigEntry(
            domain=DOMAIN, unique_id=ATTR_SERIAL_NUMBER, data=CONFIG
        ).add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context=CONTEXT_USER, data=CONFIG
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
