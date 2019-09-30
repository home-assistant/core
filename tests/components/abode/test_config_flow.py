"""Tests for the Abode config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.abode import config_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME


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

    with patch.object(hass.config_entries, "async_entries"):
        result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_invalid_credentials(hass):
    """Test that invalid credentials throws an error."""
    from abodepy.exceptions import AbodeAuthenticationException

    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    with patch("abodepy.Abode", side_effect=AbodeAuthenticationException("errors")):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {"base": "invalid_credentials"}


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    with patch("abodepy.Abode"):
        result = await flow.async_step_import(import_config=conf)
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
        }


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.AbodeFlowHandler()
    flow.hass = hass

    with patch("abodepy.Abode"):
        result = await flow.async_step_user(user_input=conf)
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
        }
