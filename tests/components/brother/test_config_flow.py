"""Define tests for the Brother Printer config flow."""
import json

from asynctest import patch
from brother import SnmpError, UnsupportedModel

from homeassistant import data_entry_flow
from homeassistant.components.brother import config_flow
from homeassistant.components.brother.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TYPE

from tests.common import load_fixture

CONFIG = {
    CONF_HOST: "localhost",
    CONF_NAME: "Printer",
    CONF_TYPE: "laser",
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.BrotherConfigFlow()
    flow.hass = hass

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_create_entry_with_hostname(hass):
    """Test that the user step works with printer hostname."""
    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        flow = config_flow.BrotherConfigFlow()
        flow.hass = hass
        flow.context = {}

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=CONFIG
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "HL-L2340DW 0123456789"
        assert result["data"][CONF_HOST] == CONFIG[CONF_HOST]
        assert result["data"][CONF_NAME] == CONFIG[CONF_NAME]


async def test_create_entry_with_ip_address(hass):
    """Test that the user step works with printer IP address."""
    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        flow = config_flow.BrotherConfigFlow()
        flow.hass = hass
        flow.context = {}

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_NAME: "Name", CONF_HOST: "127.0.0.1", CONF_TYPE: "laser"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "HL-L2340DW 0123456789"
        assert result["data"][CONF_HOST] == "127.0.0.1"
        assert result["data"][CONF_NAME] == "Name"


async def test_invalid_hostname(hass):
    """Test invalid hostname in user_input."""
    flow = config_flow.BrotherConfigFlow()
    flow.hass = hass

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={CONF_NAME: "Name", CONF_HOST: "invalid/hostname", CONF_TYPE: "laser"},
    )

    assert result["errors"] == {CONF_HOST: "wrong_host"}


async def test_connection_error(hass):
    """Test connection to host error."""
    with patch("brother.Brother._get_data", side_effect=ConnectionError()):
        flow = config_flow.BrotherConfigFlow()
        flow.hass = hass

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=CONFIG
        )

        assert result["errors"] == {"base": "connection_error"}


async def test_snmp_error(hass):
    """Test SNMP error."""
    with patch("brother.Brother._get_data", side_effect=SnmpError("error")):
        flow = config_flow.BrotherConfigFlow()
        flow.hass = hass

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=CONFIG
        )

        assert result["errors"] == {"base": "snmp_error"}


async def test_unsupported_model_error(hass):
    """Test unsupported printer model error."""
    with patch("brother.Brother._get_data", side_effect=UnsupportedModel("error")):
        flow = config_flow.BrotherConfigFlow()
        flow.hass = hass

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "unsupported_model"
