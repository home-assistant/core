"""Tests for the Meteo-France config flow."""
from unittest.mock import patch

from meteofrance.client import meteofranceError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.meteo_france.const import CONF_CITY, DOMAIN, SENSOR_TYPES
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_MONITORED_CONDITIONS

from tests.common import MockConfigEntry

CITY = "74220"
CITY_2 = "69004"
MONITORED_CONDITIONS = ["temperature", "weather"]
DEFAULT_MONITORED_CONDITIONS = list(SENSOR_TYPES)


@pytest.fixture(name="client")
def mock_controller_client():
    """Mock a successful client."""
    with patch("meteofrance.client.meteofranceClient", update=False):
        yield


async def test_user(hass, client):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=None,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_CITY: CITY},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == CITY
    assert result["title"] == CITY
    assert result["data"][CONF_CITY] == CITY
    assert result["data"][CONF_MONITORED_CONDITIONS] == DEFAULT_MONITORED_CONDITIONS


async def test_import(hass, client):
    """Test import step."""
    # import with city
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_CITY: CITY},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == CITY
    assert result["title"] == CITY
    assert result["data"][CONF_CITY] == CITY
    assert result["data"][CONF_MONITORED_CONDITIONS] == DEFAULT_MONITORED_CONDITIONS

    # import with all
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_CITY: CITY_2, CONF_MONITORED_CONDITIONS: MONITORED_CONDITIONS},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == CITY_2
    assert result["title"] == CITY_2
    assert result["data"][CONF_CITY] == CITY_2
    assert result["data"][CONF_MONITORED_CONDITIONS] == MONITORED_CONDITIONS


async def test_abort_if_already_setup(hass, client):
    """Test we abort if already setup."""
    MockConfigEntry(domain=DOMAIN, data={CONF_CITY: CITY}, unique_id=CITY).add_to_hass(
        hass
    )

    # Should fail, same CITY (import)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_CITY: CITY},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same CITY (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_CITY: CITY},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_on_client_failed(hass):
    """Test when we have errors during client fetch."""
    with patch(
        "homeassistant.components.meteo_france.config_flow.meteofranceClient",
        side_effect=meteofranceError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_CITY: CITY},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}
