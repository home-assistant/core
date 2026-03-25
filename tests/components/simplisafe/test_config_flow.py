"""Define tests for the SimpliSafe config flow."""

import logging
from unittest.mock import patch

import pytest
from simplipy.errors import InvalidCredentialsError, SimplipyError

from homeassistant.components.simplisafe import DOMAIN
from homeassistant.components.simplisafe.config_flow import CONF_AUTH_CODE
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VALID_AUTH_CODE = "code12345123451234512345123451234512345123451"


async def test_duplicate_error(
    config_entry, hass: HomeAssistant, setup_simplisafe
) -> None:
    """Test that errors are shown when duplicates are added."""
    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: VALID_AUTH_CODE}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_invalid_auth_code_length(hass: HomeAssistant) -> None:
    """Test that an invalid auth code length show the correct error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_AUTH_CODE: "too_short_code"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_AUTH_CODE: "invalid_auth_code_length"}


async def test_invalid_credentials(hass: HomeAssistant) -> None:
    """Test that invalid credentials show the correct error."""
    with patch(
        "homeassistant.components.simplisafe.config_flow.API.async_from_auth",
        side_effect=InvalidCredentialsError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_AUTH_CODE: VALID_AUTH_CODE},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_AUTH_CODE: "invalid_auth"}


async def test_options_flow(config_entry, hass: HomeAssistant) -> None:
    """Test config flow options."""
    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_CODE: "4321"}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert config_entry.options == {CONF_CODE: "4321"}


async def test_step_reauth(
    config_entry: MockConfigEntry, hass: HomeAssistant, setup_simplisafe
) -> None:
    """Test the re-auth step."""
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.simplisafe.async_setup_entry", return_value=True
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: VALID_AUTH_CODE}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    [config_entry] = hass.config_entries.async_entries(DOMAIN)
    assert config_entry.data == {CONF_USERNAME: "12345", CONF_TOKEN: "token123"}


@pytest.mark.parametrize("unique_id", ["some_other_id"])
async def test_step_reauth_wrong_account(
    config_entry: MockConfigEntry, hass: HomeAssistant, setup_simplisafe
) -> None:
    """Test the re-auth step where the wrong account is used during login."""
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.simplisafe.async_setup_entry", return_value=True
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: VALID_AUTH_CODE}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "wrong_account"


@pytest.mark.parametrize(
    ("auth_code", "log_statement"),
    [
        (
            VALID_AUTH_CODE,
            None,
        ),
        (
            f"={VALID_AUTH_CODE}",
            'Stripping "=" from the start of the authorization code',
        ),
    ],
)
async def test_step_user(
    auth_code,
    caplog: pytest.LogCaptureFixture,
    hass: HomeAssistant,
    log_statement,
    setup_simplisafe,
) -> None:
    """Test successfully completion of the user step."""
    caplog.set_level = logging.DEBUG

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.simplisafe.async_setup_entry", return_value=True
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: auth_code}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

    if log_statement:
        assert any(m for m in caplog.messages if log_statement in m)

    assert len(hass.config_entries.async_entries()) == 1
    [config_entry] = hass.config_entries.async_entries(DOMAIN)
    assert config_entry.data == {CONF_USERNAME: "12345", CONF_TOKEN: "token123"}


async def test_unknown_error(hass: HomeAssistant, setup_simplisafe) -> None:
    """Test that an unknown error shows ohe correct error."""
    with patch(
        "homeassistant.components.simplisafe.config_flow.API.async_from_auth",
        side_effect=SimplipyError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "user"
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_AUTH_CODE: VALID_AUTH_CODE}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
