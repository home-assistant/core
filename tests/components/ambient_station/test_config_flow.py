"""Define tests for the Ambient PWS config flow."""
import json
from unittest.mock import patch

import aioambient
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.ambient_station import CONF_APP_KEY, DOMAIN, config_flow
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry, load_fixture, mock_coro


@pytest.fixture
def get_devices_response():
    """Define a fixture for a successful /devices response."""
    return mock_coro()


@pytest.fixture
def mock_aioambient(get_devices_response):
    """Mock the aioambient library."""
    with patch("homeassistant.components.ambient_station.config_flow.Client") as Client:
        Client().api.get_devices.return_value = get_devices_response
        yield Client


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_API_KEY: "12345abcde12345abcde", CONF_APP_KEY: "67890fghij67890fghij"}

    MockConfigEntry(
        domain=DOMAIN, unique_id="67890fghij67890fghij", data=conf
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "get_devices_response", [mock_coro(exception=aioambient.errors.AmbientError)]
)
async def test_invalid_api_key(hass, mock_aioambient):
    """Test that an invalid API/App Key throws an error."""
    conf = {CONF_API_KEY: "12345abcde12345abcde", CONF_APP_KEY: "67890fghij67890fghij"}

    flow = config_flow.AmbientStationFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {"base": "invalid_key"}


@pytest.mark.parametrize("get_devices_response", [mock_coro(return_value=[])])
async def test_no_devices(hass, mock_aioambient):
    """Test that an account with no associated devices throws an error."""
    conf = {CONF_API_KEY: "12345abcde12345abcde", CONF_APP_KEY: "67890fghij67890fghij"}

    flow = config_flow.AmbientStationFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {"base": "no_devices"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.AmbientStationFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


@pytest.mark.parametrize(
    "get_devices_response",
    [mock_coro(return_value=json.loads(load_fixture("ambient_devices.json")))],
)
async def test_step_import(hass, mock_aioambient):
    """Test that the import step works."""
    conf = {CONF_API_KEY: "12345abcde12345abcde", CONF_APP_KEY: "67890fghij67890fghij"}

    flow = config_flow.AmbientStationFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_import(import_config=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "67890fghij67"
    assert result["data"] == {
        CONF_API_KEY: "12345abcde12345abcde",
        CONF_APP_KEY: "67890fghij67890fghij",
    }


@pytest.mark.parametrize(
    "get_devices_response",
    [mock_coro(return_value=json.loads(load_fixture("ambient_devices.json")))],
)
async def test_step_user(hass, mock_aioambient):
    """Test that the user step works."""
    conf = {CONF_API_KEY: "12345abcde12345abcde", CONF_APP_KEY: "67890fghij67890fghij"}

    flow = config_flow.AmbientStationFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user(user_input=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "67890fghij67"
    assert result["data"] == {
        CONF_API_KEY: "12345abcde12345abcde",
        CONF_APP_KEY: "67890fghij67890fghij",
    }
