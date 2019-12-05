"""Tests for the Meteo-France config flow."""
from unittest.mock import patch

from meteofrance.client import meteofranceError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.meteo_france import config_flow
from homeassistant.components.meteo_france.const import CONF_CITY, DOMAIN, SENSOR_TYPES
from homeassistant.const import CONF_MONITORED_CONDITIONS

from tests.common import MockConfigEntry

CITY = "74220"
MONITORED_CONDITIONS = ["temperature", "weather"]
DEFAULT_MONITORED_CONDITIONS = list(SENSOR_TYPES)


@pytest.fixture(name="client")
def mock_controller_client():
    """Mock a successful client."""
    with patch("meteofrance.client.meteofranceClient", update=False):
        yield


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.MeteoFranceFlowHandler()
    flow.hass = hass
    return flow


async def test_user(hass, client):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await flow.async_step_user({CONF_CITY: CITY})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == CITY
    assert result["data"][CONF_CITY] == CITY
    assert result["data"][CONF_MONITORED_CONDITIONS] == DEFAULT_MONITORED_CONDITIONS


async def test_import(hass, client):
    """Test import step."""
    flow = init_config_flow(hass)

    # import with city
    result = await flow.async_step_import({CONF_CITY: CITY})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == CITY
    assert result["data"][CONF_CITY] == CITY
    assert result["data"][CONF_MONITORED_CONDITIONS] == DEFAULT_MONITORED_CONDITIONS

    # import with all
    result = await flow.async_step_import(
        {CONF_CITY: CITY, CONF_MONITORED_CONDITIONS: MONITORED_CONDITIONS}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == CITY
    assert result["data"][CONF_CITY] == CITY
    assert result["data"][CONF_MONITORED_CONDITIONS] == MONITORED_CONDITIONS


async def test_abort_if_already_setup(hass, client):
    """Test we abort if already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(domain=DOMAIN, data={CONF_CITY: CITY}).add_to_hass(hass)

    # Should fail, same CITY (import)
    result = await flow.async_step_import({CONF_CITY: CITY})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "city_exists"

    # Should fail, same CITY (flow)
    result = await flow.async_step_user({CONF_CITY: CITY})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_CITY: "city_exists"}


async def test_on_client_failed(hass):
    """Test when we have errors during client fetch."""
    flow = init_config_flow(hass)

    with patch(
        "meteofrance.client.meteofranceClient._init_codes",
        side_effect=meteofranceError(),
    ):
        result = await flow.async_step_user({CONF_CITY: CITY})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}
