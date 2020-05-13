"""Test the Garmin Connect config flow."""
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.garmin_connect.const import DOMAIN
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import patch
from tests.common import MockConfigEntry

MOCK_CONF = {
    CONF_ID: "First Lastname",
    CONF_USERNAME: "my@email.address",
    CONF_PASSWORD: "mypassw0rd",
}


@pytest.fixture(name="mock_garmin_connect")
def mock_garmin():
    """Mock Garmin."""
    with patch("homeassistant.components.garmin_connect.config_flow.Garmin",) as garmin:
        garmin.return_value.get_full_name.return_value = MOCK_CONF[CONF_ID]
        yield garmin.return_value


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_user(hass, mock_garmin_connect):
    """Test registering an integration and finishing flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_CONF
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == MOCK_CONF


async def test_connection_error(hass, mock_garmin_connect):
    """Test for connection error."""
    mock_garmin_connect.login.side_effect = GarminConnectConnectionError("errormsg")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_CONF
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_authentication_error(hass, mock_garmin_connect):
    """Test for authentication error."""
    mock_garmin_connect.login.side_effect = GarminConnectAuthenticationError("errormsg")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_CONF
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_toomanyrequest_error(hass, mock_garmin_connect):
    """Test for toomanyrequests error."""
    mock_garmin_connect.login.side_effect = GarminConnectTooManyRequestsError(
        "errormsg"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_CONF
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "too_many_requests"}


async def test_unknown_error(hass, mock_garmin_connect):
    """Test for unknown error."""
    mock_garmin_connect.login.side_effect = Exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_CONF
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}


async def test_abort_if_already_setup(hass, mock_garmin_connect):
    """Test abort if already setup."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONF, unique_id=MOCK_CONF[CONF_ID])
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_CONF
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
