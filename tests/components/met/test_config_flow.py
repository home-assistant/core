"""Tests for Met config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.met import config_flow
from homeassistant.components.met.const import (
    CONF_TRACK_HOME,
    DOMAIN,
    HOME_LOCATION_NAME,
)
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

from tests.common import MockConfigEntry

TEST_DATA = {
    CONF_NAME: "home",
    CONF_LONGITUDE: "0",
    CONF_LATITUDE: "0",
    CONF_ELEVATION: "0",
}


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.MetFlowHandler()
    flow.hass = hass
    return flow


async def test_flow_with_home_location(hass):
    """Test config flow.

    Test the flow when a default location is configured.
    Then it should return a form with default values.
    """
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    default_data = result["data_schema"]({})
    assert default_data["name"] == HOME_LOCATION_NAME
    assert default_data["latitude"] == 1
    assert default_data["longitude"] == 2
    assert default_data["elevation"] == 3

async def test_flow_show_form(hass):
    """Test show form scenarios first time.

    Test when the form should show when no configurations exists
    """
    hass.config.latitude = None
    hass.config.longitude = None
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_flow_entry_created_from_user_input(hass):
    """Test that create data from user input."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user(TEST_DATA)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == TEST_DATA[CONF_NAME]
    assert result["data"] == TEST_DATA


async def test_flow_entry_config_entry_already_exists(hass):
    """Test that create data from user input and config_entry already exists.

    Test when the form should show when user puts existing location
    in the config gui. Then the form should show with error.
    """
    flow = init_config_flow(hass)

    MockConfigEntry(domain=DOMAIN, data=TEST_DATA).add_to_hass(hass)

    result = await flow.async_step_user(user_input=TEST_DATA)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_NAME: "name_exists"}


async def test_onboarding_step(hass, mock_weather):
    """Test initializing via onboarding step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_onboarding({})

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOME_LOCATION_NAME
    assert result["data"] == {CONF_TRACK_HOME: True}
