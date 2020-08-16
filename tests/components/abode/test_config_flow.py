"""Tests for the Abode config flow."""
from abodepy.exceptions import AbodeAuthenticationException

from homeassistant import data_entry_flow
from homeassistant.components.abode import config_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, HTTP_INTERNAL_SERVER_ERROR

from tests.async_mock import patch
from tests.common import MockConfigEntry

CONF_POLLING = "polling"


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_one_config_allowed(hass):
    """Test that only one Abode configuration is allowed."""
    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    MockConfigEntry(
        domain="abode",
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    ).add_to_hass(hass)

    step_user_result = await flow.async_step_user()

    assert step_user_result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert step_user_result["reason"] == "single_instance_allowed"

    conf = {
        CONF_USERNAME: "user@email.com",
        CONF_PASSWORD: "password",
        CONF_POLLING: False,
    }

    import_config_result = await flow.async_step_import(conf)

    assert import_config_result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert import_config_result["reason"] == "single_instance_allowed"


async def test_invalid_credentials(hass):
    """Test that invalid credentials throws an error."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.abode.config_flow.Abode",
        side_effect=AbodeAuthenticationException((400, "auth error")),
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {"base": "invalid_credentials"}


async def test_connection_error(hass):
    """Test other than invalid credentials throws an error."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.abode.config_flow.Abode",
        side_effect=AbodeAuthenticationException(
            (HTTP_INTERNAL_SERVER_ERROR, "connection error")
        ),
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {"base": "connection_error"}


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {
        CONF_USERNAME: "user@email.com",
        CONF_PASSWORD: "password",
        CONF_POLLING: False,
    }

    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    with patch("homeassistant.components.abode.config_flow.Abode"):
        result = await flow.async_step_import(import_config=conf)
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        result = await flow.async_step_user(user_input=result["data"])
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
            CONF_POLLING: False,
        }


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    with patch("homeassistant.components.abode.config_flow.Abode"):
        result = await flow.async_step_user(user_input=conf)
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
            CONF_POLLING: False,
        }
