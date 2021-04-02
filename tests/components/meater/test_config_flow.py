"""Define tests for the Meater config flow."""
from unittest.mock import AsyncMock, patch

from meater import AuthenticationError, ServiceUnavailableError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.meater import DOMAIN, config_flow
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_client():
    """Define a fixture for authentication coroutine."""
    return AsyncMock(return_value=None)


@pytest.fixture
def mock_meater(mock_client):
    """Mock the meater library."""
    with patch("homeassistant.components.meater.MeaterApi.authenticate") as mock_:
        mock_.side_effect = mock_client
        yield mock_


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    MockConfigEntry(domain=DOMAIN, unique_id="user@host.com", data=conf).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("mock_client", [AsyncMock(side_effect=Exception)])
async def test_unknown_auth_error(hass, mock_meater):
    """Test that an invalid API/App Key throws an error."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    flow = config_flow.MeaterConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {"base": "unknown_auth_error"}


@pytest.mark.parametrize("mock_client", [AsyncMock(side_effect=AuthenticationError)])
async def test_invalid_credentials(hass, mock_meater):
    """Test that an invalid API/App Key throws an error."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    flow = config_flow.MeaterConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize(
    "mock_client", [AsyncMock(side_effect=ServiceUnavailableError)]
)
async def test_service_unavailable(hass, mock_meater):
    """Test that an invalid API/App Key throws an error."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    flow = config_flow.MeaterConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {"base": "service_unavailable_error"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.MeaterConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_user(hass, mock_meater):
    """Test that the user step works."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    flow = config_flow.MeaterConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user(user_input=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "password123",
    }
