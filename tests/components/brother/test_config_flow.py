"""Define tests for the Brother Printer config flow."""
import json
import logging

from asynctest import patch
from brother import SnmpError, UnsupportedModel

from homeassistant import data_entry_flow
from homeassistant.components.brother import config_flow
from homeassistant.components.brother.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TYPE

from tests.common import MockConfigEntry, load_fixture

_LOGGER = logging.getLogger(__name__)


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.BrotherConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_create_entry_with_hostname(hass):
    """Test that the user step works with printer hostname."""
    config = {
        CONF_HOST: "localhost",
        CONF_NAME: "Printer",
        CONF_TYPE: "laser",
    }

    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        flow = config_flow.BrotherConfigFlow()
        flow.hass = hass

        result = await flow.async_step_user(user_input=config)

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "HL-L2340DW 0123456789"
        assert result["data"][CONF_HOST] == config[CONF_HOST]
        assert result["data"][CONF_NAME] == config[CONF_NAME]


async def test_create_entry_with_ip_address(hass):
    """Test that the user step works with printer IP address."""
    config = {
        CONF_HOST: "localhost",
        CONF_NAME: "Printer",
        CONF_TYPE: "laser",
    }

    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        flow = config_flow.BrotherConfigFlow()
        flow.hass = hass

        config[CONF_HOST] = "127.0.0.1"
        result = await flow.async_step_user(user_input=config)

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "HL-L2340DW 0123456789"
        assert result["data"][CONF_HOST] == config[CONF_HOST]
        assert result["data"][CONF_NAME] == config[CONF_NAME]


async def test_invalid_hostname(hass):
    """Test invalid hostname in user_input."""
    config = {
        CONF_HOST: "localhost",
        CONF_NAME: "Printer",
        CONF_TYPE: "laser",
    }

    flow = config_flow.BrotherConfigFlow()
    flow.hass = hass

    config[CONF_HOST] = "invalid/hostname"
    result = await flow.async_step_user(user_input=config)

    assert result["errors"] == {CONF_HOST: "wrong_host"}


async def test_duplicate_name_error(hass):
    """Test that errors are shown when duplicate name are added."""
    config = {
        CONF_HOST: "localhost",
        CONF_NAME: "Printer",
        CONF_TYPE: "laser",
    }

    with patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("brother_printer_data.json")),
    ):
        MockConfigEntry(domain=DOMAIN, data=config).add_to_hass(hass)
        flow = config_flow.BrotherConfigFlow()
        flow.hass = hass

        result = await flow.async_step_user(user_input=config)

        assert result["errors"] == {CONF_NAME: "name_exists"}


async def test_connection_error(hass):
    """Test connection to host error."""
    config = {
        CONF_HOST: "localhost",
        CONF_NAME: "Printer",
        CONF_TYPE: "laser",
    }

    with patch("brother.Brother._get_data", side_effect=ConnectionError()):
        flow = config_flow.BrotherConfigFlow()
        flow.hass = hass

        result = await flow.async_step_user(user_input=config)

        assert result["errors"] == {"base": "connection_error"}


async def test_snmp_error(hass):
    """Test SNMP error."""
    config = {
        CONF_HOST: "localhost",
        CONF_NAME: "Printer",
        CONF_TYPE: "laser",
    }

    with patch("brother.Brother._get_data", side_effect=SnmpError("error")):
        flow = config_flow.BrotherConfigFlow()
        flow.hass = hass

        result = await flow.async_step_user(user_input=config)

        assert result["errors"] == {"base": "snmp_error"}


async def test_unsupported_model_error(hass):
    """Test unsupported printer model error."""
    config = {
        CONF_HOST: "localhost",
        CONF_NAME: "Printer",
        CONF_TYPE: "laser",
    }

    with patch("brother.Brother._get_data", side_effect=UnsupportedModel("error")):
        flow = config_flow.BrotherConfigFlow()
        flow.hass = hass

        result = await flow.async_step_user(user_input=config)

        assert result["type"] == "abort"
        assert result["reason"] == "unsupported_model"
