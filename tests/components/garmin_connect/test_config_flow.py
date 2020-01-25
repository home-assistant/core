"""Test the Garmin Connect config flow."""
from unittest.mock import patch

from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
import pytest

from homeassistant.components.garmin_connect.const import DOMAIN
from homeassistant import data_entry_flow
from homeassistant.components.garmin_connect import config_flow
from homeassistant.const import (
    CONF_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry

MOCK_CONF = {
    CONF_ID: "First Lastname",
    CONF_USERNAME: "my@email.address",
    CONF_PASSWORD: "mypassw0rd",
}


@pytest.fixture(name="mock_garmin_connect")
def mock_garminconnect():
    """Mock Garmin."""
    with patch("homeassistant.components.garmin_connect.config_flow.Garmin") as garmin:
        garmin().get_full_name.return_value = "First Lastname"
        yield garmin


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.GarminConnectConfigFlowHandler()
    flow.hass = hass
    return flow


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_user(hass, mock_garmin_connect):
    """Test registering an integration and finishing flow works."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user(user_input=MOCK_CONF)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "First Lastname"
    assert result["data"] == MOCK_CONF


async def test_connection_error(hass):
    """Test for connection error."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.garmin_connect.config_flow.Garmin",
        side_effect=GarminConnectConnectionError("errormsg"),
    ):
        result = await flow.async_step_user(MOCK_CONF)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_authentication_error(hass):
    """Test for authentication error."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.garmin_connect.config_flow.Garmin",
        side_effect=GarminConnectAuthenticationError("errormsg"),
    ):
        result = await flow.async_step_user(MOCK_CONF)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_toomanyrequest_error(hass):
    """Test for toomanyrequests error."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.garmin_connect.config_flow.Garmin",
        side_effect=GarminConnectTooManyRequestsError("errormsg"),
    ):
        result = await flow.async_step_user(MOCK_CONF)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "too_many_requests"}


async def test_unknown_error(hass):
    """Test for unknown error."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.garmin_connect.config_flow.Garmin",
        side_effect=Exception(),
    ):
        result = await flow.async_step_user(MOCK_CONF)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}


async def test_abort_if_already_setup(hass, mock_garmin_connect):
    """Test abort if already setup."""
    flow = init_config_flow(hass)

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONF)
    entry.add_to_hass(hass)

    result = await flow.async_step_user(MOCK_CONF)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"
