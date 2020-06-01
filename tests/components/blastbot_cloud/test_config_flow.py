"""Tests for the Blastbot Cloud config flow."""
from aiohttp import ClientError

from homeassistant import data_entry_flow
from homeassistant.components.blastbot_cloud import config_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, HTTP_INTERNAL_SERVER_ERROR

from tests.async_mock import patch


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.BlastbotCloudConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_invalid_credentials(hass):
    """Test that invalid credentials throws an error."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.BlastbotCloudConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.blastbot_cloud.config_flow.BlastbotCloudAPI.async_login",
        return_value=False,
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {"base": "invalid_credentials"}


async def test_connection_error(hass):
    """Test other than invalid credentials throws an error."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.BlastbotCloudConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.blastbot_cloud.config_flow.BlastbotCloudAPI.async_login",
        side_effect=ClientError((HTTP_INTERNAL_SERVER_ERROR, "connection error")),
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {"base": "connection_error"}


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"}

    flow = config_flow.BlastbotCloudConfigFlow()
    flow.hass = hass
    flow.context = {}

    with patch(
        "homeassistant.components.blastbot_cloud.config_flow.BlastbotCloudAPI.async_login",
        return_value=True,
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
        }
