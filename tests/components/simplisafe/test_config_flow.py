"""Define tests for the SimpliSafe config flow."""
from unittest.mock import patch

import pytest
from simplipy.errors import InvalidCredentialsError, SimplipyError

from homeassistant import data_entry_flow
from homeassistant.components.simplisafe import DOMAIN
from homeassistant.components.simplisafe.config_flow import CONF_AUTH_CODE
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_TOKEN, CONF_USERNAME


async def test_duplicate_error(config_entry, hass, setup_simplisafe):
    """Test that errors are shown when duplicates are added."""
    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_invalid_credentials(hass):
    """Test that invalid credentials show the correct error."""
    with patch(
        "homeassistant.components.simplisafe.config_flow.API.async_from_auth",
        side_effect=InvalidCredentialsError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow(config_entry, hass):
    """Test config flow options."""
    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_CODE: "4321"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_CODE: "4321"}


async def test_step_reauth(config_entry, hass, setup_simplisafe):
    """Test the re-auth step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH},
        data={CONF_USERNAME: "12345", CONF_TOKEN: "token123"},
    )
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ), patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    [config_entry] = hass.config_entries.async_entries(DOMAIN)
    assert config_entry.data == {CONF_USERNAME: "12345", CONF_TOKEN: "token123"}


@pytest.mark.parametrize("unique_id", ["some_other_id"])
async def test_step_reauth_wrong_account(config_entry, hass, setup_simplisafe):
    """Test the re-auth step where the wrong account is used during login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH},
        data={CONF_USERNAME: "12345", CONF_TOKEN: "token123"},
    )
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ), patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "wrong_account"


async def test_step_user(hass, setup_simplisafe):
    """Test the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ), patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    assert len(hass.config_entries.async_entries()) == 1
    [config_entry] = hass.config_entries.async_entries(DOMAIN)
    assert config_entry.data == {CONF_USERNAME: "12345", CONF_TOKEN: "token123"}


async def test_unknown_error(hass, setup_simplisafe):
    """Test that an unknown error shows ohe correct error."""
    with patch(
        "homeassistant.components.simplisafe.config_flow.API.async_from_auth",
        side_effect=SimplipyError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: "code123"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}
