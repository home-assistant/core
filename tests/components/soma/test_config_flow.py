"""Tests for the Soma config flow."""
from api.soma_api import SomaApi
from requests import RequestException

from homeassistant import data_entry_flow
from homeassistant.components.soma import DOMAIN, config_flow

from tests.async_mock import patch
from tests.common import MockConfigEntry

MOCK_HOST = "123.45.67.89"
MOCK_PORT = 3000


async def test_form(hass):
    """Test user form showing."""
    flow = config_flow.SomaFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_import_abort(hass):
    """Test configuration from YAML aborting with existing entity."""
    flow = config_flow.SomaFlowHandler()
    flow.hass = hass
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)
    result = await flow.async_step_import()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"


async def test_import_create(hass):
    """Test configuration from YAML."""
    flow = config_flow.SomaFlowHandler()
    flow.hass = hass
    with patch.object(SomaApi, "list_devices", return_value={"result": "success"}):
        result = await flow.async_step_import({"host": MOCK_HOST, "port": MOCK_PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_error_status(hass):
    """Test Connect successfully returning error status."""
    flow = config_flow.SomaFlowHandler()
    flow.hass = hass
    with patch.object(SomaApi, "list_devices", return_value={"result": "error"}):
        result = await flow.async_step_import({"host": MOCK_HOST, "port": MOCK_PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "result_error"


async def test_key_error(hass):
    """Test Connect returning empty string."""
    flow = config_flow.SomaFlowHandler()
    flow.hass = hass
    with patch.object(SomaApi, "list_devices", return_value={}):
        result = await flow.async_step_import({"host": MOCK_HOST, "port": MOCK_PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "connection_error"


async def test_exception(hass):
    """Test if RequestException fires when no connection can be made."""
    flow = config_flow.SomaFlowHandler()
    flow.hass = hass
    with patch.object(SomaApi, "list_devices", side_effect=RequestException()):
        result = await flow.async_step_import({"host": MOCK_HOST, "port": MOCK_PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "connection_error"


async def test_full_flow(hass):
    """Check classic use case."""
    hass.data[DOMAIN] = {}
    flow = config_flow.SomaFlowHandler()
    flow.hass = hass
    with patch.object(SomaApi, "list_devices", return_value={"result": "success"}):
        result = await flow.async_step_user({"host": MOCK_HOST, "port": MOCK_PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
