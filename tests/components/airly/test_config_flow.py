"""Define tests for the Airly config flow."""
import pytest

from homeassistant import data_entry_flow
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.components.airly import config_flow
from homeassistant.components.airly.const import CONF_LANGUAGE, DOMAIN

from tests.common import MockConfigEntry, MockDependency

CONFIG = {
    CONF_NAME: "abcd",
    CONF_API_KEY: "foo",
    CONF_LATITUDE: 0,
    CONF_LONGITUDE: 0,
    CONF_LANGUAGE: "en",
}


@pytest.fixture
def mock_airly():
    """Mock the airly library."""
    with MockDependency("airly") as mock_airly_:
        yield mock_airly_


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.AirlyFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_show_form_with_input(hass):
    """Test that the form is served with input."""
    flow = config_flow.AirlyFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=CONFIG)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_invalid_api_key(hass, mock_airly):
    """Test that an invalid API_KEY throws an error."""
    flow = config_flow.AirlyFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=CONFIG)
    assert result["errors"] == {"base": "auth"}


async def test_invalid_language(hass, mock_airly):
    """Test that errors are shown when language is invalid."""
    conf = {
        CONF_NAME: "abcd",
        CONF_API_KEY: "foo",
        CONF_LATITUDE: 0,
        CONF_LONGITUDE: 0,
        CONF_LANGUAGE: "invalid",
    }

    flow = config_flow.AirlyFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {CONF_LANGUAGE: "wrong_lang", "base": "auth"}


async def test_duplicate_error(hass, mock_airly):
    """Test that errors are shown when duplicates are added."""
    MockConfigEntry(domain=DOMAIN, data=CONFIG).add_to_hass(hass)
    flow = config_flow.AirlyFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=CONFIG)
    assert result["errors"] == {CONF_NAME: "name_exists", "base": "auth"}
