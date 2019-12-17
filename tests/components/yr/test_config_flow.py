"""Tests for the Yr config flow."""
from datetime import datetime
from unittest.mock import patch

import aiohttp
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.yr import config_flow
from homeassistant.components.yr.const import (
    API_URL,
    CONF_FORECAST,
    DEFAULT_FORECAST,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

NOW = datetime(2016, 6, 9, 1, tzinfo=dt_util.UTC)

NAME = "La Clusaz"
FORECAST = 24
ELEVATION = 1326
LATITUDE = 45.904498
LONGITUDE = 6.424547


@pytest.fixture(name="data")
def mock_controller_data(aioclient_mock: AiohttpClientMocker):
    """Mock a successful data."""
    aioclient_mock.get(
        API_URL, text=load_fixture("yr.no.xml"),
    )
    with patch("homeassistant.components.yr.sensor.dt_util.utcnow", return_value=NOW):
        yield


@pytest.fixture(name="data_failed")
def mock_controller_data_failed(aioclient_mock: AiohttpClientMocker):
    """Mock a failed data."""
    aioclient_mock.get(
        API_URL, exc=aiohttp.ClientError,
    )


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.YrFlowHandler()
    flow.hass = hass
    return flow


async def test_user(hass, data):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_NAME] == DEFAULT_NAME


async def test_import(hass, data):
    """Test import step."""
    flow = init_config_flow(hass)

    # import empty
    result = await flow.async_step_import({CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_ELEVATION] == 0
    assert result["data"][CONF_FORECAST] == DEFAULT_FORECAST
    assert result["data"][CONF_LATITUDE] == 32.87336
    assert result["data"][CONF_LONGITUDE] == -117.22743

    # import with all
    result = await flow.async_step_import(
        {
            CONF_NAME: NAME,
            CONF_ELEVATION: ELEVATION,
            CONF_FORECAST: FORECAST,
            CONF_LATITUDE: LATITUDE,
            CONF_LONGITUDE: LONGITUDE,
        }
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_ELEVATION] == ELEVATION
    assert result["data"][CONF_FORECAST] == FORECAST
    assert result["data"][CONF_LATITUDE] == LATITUDE
    assert result["data"][CONF_LONGITUDE] == LONGITUDE


async def test_abort_if_already_setup(hass, data):
    """Test we abort if Yr is already setup."""
    flow = init_config_flow(hass)

    # Should fail, default (import)
    MockConfigEntry(domain=DOMAIN, data={CONF_NAME: DEFAULT_NAME}).add_to_hass(hass)

    result = await flow.async_step_import({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "name_exists"

    # Should fail, same NAME (flow)
    result = await flow.async_step_user({CONF_NAME: DEFAULT_NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "name_exists"}


async def test_abort_if_no_coordinates(hass, data):
    """Test we abort if Yr has no coordinates."""
    hass.config.latitude = None
    hass.config.longitude = None
    flow = init_config_flow(hass)

    # Should fail, no coordinates (import)
    result = await flow.async_step_import({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "coordinates_not_set"

    # Should fail, no coordinates (flow)
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "coordinates_not_set"}


async def test_abort_if_data_failed(hass, data_failed):
    """Test we abort if Yr has data failure."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}
