"""Define tests for the SimpliSafe config flow."""
from unittest.mock import patch

import pytest
from simplipy.errors import InvalidCredentialsError, SimplipyError

from homeassistant import data_entry_flow
from homeassistant.components.simplisafe import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_CODE


async def test_duplicate_error(hass, config_entry, config_code, setup_simplisafe):
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config_code
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "exc,error_string",
    [(InvalidCredentialsError, "invalid_auth"), (SimplipyError, "unknown")],
)
async def test_errors(hass, config_code, exc, error_string):
    """Test that exceptions show the appropriate error."""
    with patch(
        "homeassistant.components.simplisafe.API.async_from_auth",
        side_effect=exc,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=config_code
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": error_string}


async def test_options_flow(hass, config_entry):
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


async def test_step_reauth_old_format(
    hass, config, config_code, config_entry, setup_simplisafe
):
    """Test the re-auth step with "old" config entries (those with user IDs)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}, data=config
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config_code
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    [config_entry] = hass.config_entries.async_entries(DOMAIN)
    assert config_entry.data == config


async def test_step_reauth_new_format(
    hass, config, config_code, config_entry, setup_simplisafe
):
    """Test the re-auth step with "new" config entries (those with user IDs)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}, data=config
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config_code
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    [config_entry] = hass.config_entries.async_entries(DOMAIN)
    assert config_entry.data == config


async def test_step_reauth_wrong_account(
    hass, api, config, config_code, config_entry, setup_simplisafe
):
    """Test the re-auth step returning a different account from this one."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}, data=config
    )
    assert result["step_id"] == "user"

    # Simulate the next auth call returning a different user ID than the one we've
    # identified as this entry's unique ID:
    api.user_id = "67890"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config_code
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "wrong_account"

    assert len(hass.config_entries.async_entries()) == 1
    [config_entry] = hass.config_entries.async_entries(DOMAIN)
    assert config_entry.unique_id == "12345"


async def test_step_user(hass, config, config_code, setup_simplisafe):
    """Test the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config_code
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    assert len(hass.config_entries.async_entries()) == 1
    [config_entry] = hass.config_entries.async_entries(DOMAIN)
    assert config_entry.data == config
