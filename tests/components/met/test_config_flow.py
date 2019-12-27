"""Tests for Met config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.met import config_flow
from homeassistant.components.met.const import (
    CONF_FORECAST,
    CONF_TRACK_HOME,
    DOMAIN,
    HOME_LOCATION_NAME,
)
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

NAME = "La Clusaz"
FORECAST = 24
ELEVATION = 1326
LATITUDE = 45.904498
LONGITUDE = 6.424547


def init_config_flow(hass: HomeAssistantType):
    """Init a configuration flow."""
    flow = config_flow.MetFlowHandler()
    flow.hass = hass
    return flow


async def test_user(hass: HomeAssistantType, mock_data):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await flow.async_step_user(
        {
            CONF_NAME: NAME,
            CONF_LATITUDE: LATITUDE,
            CONF_LONGITUDE: LONGITUDE,
            CONF_ELEVATION: ELEVATION,
            CONF_FORECAST: FORECAST,
        }
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_LATITUDE] == LATITUDE
    assert result["data"][CONF_LONGITUDE] == LONGITUDE
    assert result["data"][CONF_ELEVATION] == ELEVATION
    assert result["data"][CONF_FORECAST] == FORECAST


async def test_abort_if_already_setup_name(hass: HomeAssistantType):
    """Test we abort if already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: hass.config.location_name}
    ).add_to_hass(hass)

    # Should fail, same NAME (flow)
    result = await flow.async_step_user({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "already_configured"}


async def test_abort_if_already_setup_coordinates(hass: HomeAssistantType):
    """Test we abort if already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain=DOMAIN, data={CONF_LATITUDE: LATITUDE, CONF_LONGITUDE: LONGITUDE}
    ).add_to_hass(hass)

    # Should fail, same LATITUDE and LONGITUDE (flow)
    result = await flow.async_step_user(
        {CONF_LATITUDE: LATITUDE, CONF_LONGITUDE: LONGITUDE}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "already_configured"}


async def test_abort_if_no_coordinates(hass: HomeAssistantType):
    """Test we abort if Met has no coordinates."""
    hass.config.latitude = None
    hass.config.longitude = None
    flow = init_config_flow(hass)

    # Should fail, no coordinates (flow)
    result = await flow.async_step_user({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "coordinates_not_set"}


async def test_abort_if_data_failed(hass: HomeAssistantType, data_failed):
    """Test we abort if Met has data failure."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}


async def test_onboarding_step(hass: HomeAssistantType):
    """Test initializing via onboarding step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_onboarding({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOME_LOCATION_NAME
    assert result["data"] == {CONF_TRACK_HOME: True}
