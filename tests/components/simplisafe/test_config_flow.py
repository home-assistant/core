"""Define tests for the SimpliSafe config flow."""
import json
from unittest.mock import MagicMock, PropertyMock, mock_open

from asynctest import patch
from simplipy.errors import SimplipyError

from homeassistant import data_entry_flow
from homeassistant.components.simplisafe import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME

from tests.common import MockConfigEntry


def mock_api():
    """Mock SimpliSafe API class."""
    api = MagicMock()
    type(api).refresh_token = PropertyMock(return_value="12345abc")
    return api


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    MockConfigEntry(domain=DOMAIN, unique_id="user@email.com", data=conf).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_credentials(hass):
    """Test that invalid credentials throws an error."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    with patch(
        "simplipy.API.login_via_credentials", side_effect=SimplipyError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["errors"] == {"base": "invalid_credentials"}


async def test_options_flow(hass):
    """Test config flow options."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="abcde12345", data=conf, options={CONF_CODE: "1234"},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_CODE: "4321"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_CODE: "4321"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {
        CONF_USERNAME: "user@email.com",
        CONF_PASSWORD: "password",
        CONF_CODE: "1234",
    }

    mop = mock_open(read_data=json.dumps({"refresh_token": "12345"}))

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ), patch("simplipy.API.login_via_credentials", return_value=mock_api()), patch(
        "homeassistant.util.json.open", mop, create=True
    ), patch(
        "homeassistant.util.json.os.open", return_value=0
    ), patch(
        "homeassistant.util.json.os.replace"
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_TOKEN: "12345abc",
            CONF_CODE: "1234",
        }


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_USERNAME: "user@email.com",
        CONF_PASSWORD: "password",
        CONF_CODE: "1234",
    }

    mop = mock_open(read_data=json.dumps({"refresh_token": "12345"}))

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ), patch("simplipy.API.login_via_credentials", return_value=mock_api()), patch(
        "homeassistant.util.json.open", mop, create=True
    ), patch(
        "homeassistant.util.json.os.open", return_value=0
    ), patch(
        "homeassistant.util.json.os.replace"
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_TOKEN: "12345abc",
            CONF_CODE: "1234",
        }
