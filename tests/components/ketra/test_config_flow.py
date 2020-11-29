"""Tests for the Ketra config flow."""
from unittest.mock import Mock

from homeassistant import data_entry_flow
from homeassistant.components.ketra import config_flow
from homeassistant.components.ketra.const import DOMAIN
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry

FAKE_ACCOUNT_INFO = {
    CONF_USERNAME: "blah",
    CONF_PASSWORD: "blah",
    CONF_CLIENT_ID: "blah",
    CONF_CLIENT_SECRET: "blah",
}


async def patched_token_request_failure(*_):
    """Simulate a token request failure."""
    return None


async def patched_token_request_success(*_):
    """Simulate a token request success."""
    oauth_request = Mock()
    oauth_request.access_token = "1234"
    return oauth_request


async def patched_get_installations_failure(*_):
    """Simulate a get installations failure."""
    return None


async def patched_get_installations_success(*_):
    """Simulate a get installations success."""
    return {"123456": "My Installation"}


async def patched_get_installations_empty(*_):
    """Simulate a get installations success that returns an empty set."""
    return {}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.KetraConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None


async def test_oauth_error_handling(hass):
    """Test that a login error is displayed when the oauth token request fails."""
    flow = config_flow.KetraConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.ketra.config_flow.OAuthTokenResponse.request_token",
        new=patched_token_request_failure,
    ):
        result = await flow.async_step_user(user_input=FAKE_ACCOUNT_INFO)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"
        assert result["errors"] == {CONF_PASSWORD: "login"}


async def test_server_connection_error_handling(hass):
    """Test that a connection error is displayed when _get_installations() returns None."""
    flow = config_flow.KetraConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.ketra.config_flow.OAuthTokenResponse.request_token",
        new=patched_token_request_success,
    ):
        with patch(
            "homeassistant.components.ketra.config_flow.KetraConfigFlow._get_installations",
            new=patched_get_installations_failure,
        ):
            result = await flow.async_step_user(user_input=FAKE_ACCOUNT_INFO)

            assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result["step_id"] == "init"
            assert result["errors"] == {"installation_id": "connection"}


async def test_show_select_installations(hass):
    """Test that the select installations form is shown."""
    flow = config_flow.KetraConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.ketra.config_flow.OAuthTokenResponse.request_token",
        new=patched_token_request_success,
    ):
        with patch(
            "homeassistant.components.ketra.config_flow.KetraConfigFlow._get_installations",
            new=patched_get_installations_success,
        ):
            result = await flow.async_step_user(user_input=FAKE_ACCOUNT_INFO)

            assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result["step_id"] == "select_installation"
            assert result["errors"] is None
            assert result["data_schema"].schema.get("installation_id").container == {
                "123456": "My Installation"
            }


async def test_abort_if_no_installations(hass):
    """Test that we abort if there are no installations available."""
    flow = config_flow.KetraConfigFlow()
    flow.hass = hass

    with patch(
        "homeassistant.components.ketra.config_flow.OAuthTokenResponse.request_token",
        new=patched_token_request_success,
    ):
        with patch(
            "homeassistant.components.ketra.config_flow.KetraConfigFlow._get_installations",
            new=patched_get_installations_empty,
        ):
            result = await flow.async_step_user(user_input=FAKE_ACCOUNT_INFO)

            assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
            assert result["reason"] == "no_installations"


async def test_abort_if_installations_configured(hass):
    """Test that the select installations form is shown."""
    flow = config_flow.KetraConfigFlow()
    flow.hass = hass

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: "12345",
            "installation_id": "123456",
            "installation_name": "my inst",
        },
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.ketra.config_flow.OAuthTokenResponse.request_token",
        new=patched_token_request_success,
    ):
        with patch(
            "homeassistant.components.ketra.config_flow.KetraConfigFlow._get_installations",
            new=patched_get_installations_success,
        ):
            result = await flow.async_step_user(user_input=FAKE_ACCOUNT_INFO)

            assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
            assert result["reason"] == "no_installations"
