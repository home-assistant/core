"""Define tests for the SimpliSafe config flow."""
import json
from unittest.mock import MagicMock, PropertyMock, mock_open, patch

from homeassistant import data_entry_flow
from homeassistant.components.simplisafe import DOMAIN, config_flow
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME

from tests.common import MockConfigEntry, mock_coro


def mock_api():
    """Mock SimpliSafe API class."""
    api = MagicMock()
    type(api).refresh_token = PropertyMock(return_value="12345abc")
    return api


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.SimpliSafeFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {CONF_USERNAME: "identifier_exists"}


async def test_invalid_credentials(hass):
    """Test that invalid credentials throws an error."""
    from simplipy.errors import SimplipyError

    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.SimpliSafeFlowHandler()
    flow.hass = hass

    with patch(
        "simplipy.API.login_via_credentials",
        return_value=mock_coro(exception=SimplipyError),
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {"base": "invalid_credentials"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.SimpliSafeFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.SimpliSafeFlowHandler()
    flow.hass = hass

    mop = mock_open(read_data=json.dumps({"refresh_token": "12345"}))

    with patch(
        "simplipy.API.login_via_credentials",
        return_value=mock_coro(return_value=mock_api()),
    ):
        with patch("homeassistant.util.json.open", mop, create=True):
            with patch("homeassistant.util.json.os.open", return_value=0):
                with patch("homeassistant.util.json.os.replace"):
                    result = await flow.async_step_import(import_config=conf)

                    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
                    assert result["title"] == "user@email.com"
                    assert result["data"] == {
                        CONF_USERNAME: "user@email.com",
                        CONF_TOKEN: "12345abc",
                    }


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_USERNAME: "user@email.com",
        CONF_PASSWORD: "password",
    }

    flow = config_flow.SimpliSafeFlowHandler()
    flow.hass = hass

    mop = mock_open(read_data=json.dumps({"refresh_token": "12345"}))

    with patch(
        "simplipy.API.login_via_credentials",
        return_value=mock_coro(return_value=mock_api()),
    ):
        with patch("homeassistant.util.json.open", mop, create=True):
            with patch("homeassistant.util.json.os.open", return_value=0):
                with patch("homeassistant.util.json.os.replace"):
                    result = await flow.async_step_user(user_input=conf)

                    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
                    assert result["title"] == "user@email.com"
                    assert result["data"] == {
                        CONF_USERNAME: "user@email.com",
                        CONF_TOKEN: "12345abc",
                    }
