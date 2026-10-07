"""Test the Cync config flow."""

from unittest.mock import ANY, AsyncMock, MagicMock

from pycync.exceptions import AuthFailedError, CyncError, TwoFactorRequiredError
import pytest

from homeassistant.components.cync.const import (
    CONF_AUTHORIZE_STRING,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_TWO_FACTOR_CODE,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCKED_EMAIL, MOCKED_USER, SECOND_MOCKED_USER

from tests.common import MockConfigEntry


async def test_form_auth_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that an auth flow without two factor succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: MOCKED_EMAIL,
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCKED_EMAIL
    assert result["data"] == {
        CONF_USER_ID: MOCKED_USER.user_id,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: ANY,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert result["result"].unique_id == str(MOCKED_USER.user_id)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_two_factor_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, auth_client: MagicMock
) -> None:
    """Test we handle a request for a two factor code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    auth_client.login.side_effect = TwoFactorRequiredError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: MOCKED_EMAIL,
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "two_factor"

    # Enter two factor code
    auth_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TWO_FACTOR_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCKED_EMAIL
    assert result["data"] == {
        CONF_USER_ID: MOCKED_USER.user_id,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: ANY,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert result["result"].unique_id == str(MOCKED_USER.user_id)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    auth_client: MagicMock,
) -> None:
    """Test we handle re-authentication with two-factor."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    auth_client.login.side_effect = TwoFactorRequiredError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: MOCKED_EMAIL,
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "two_factor"

    # Enter two factor code
    auth_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TWO_FACTOR_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_USER_ID: MOCKED_USER.user_id,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: ANY,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_reauth_unique_id_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    auth_client: MagicMock,
) -> None:
    """Test we handle a unique ID mismatch when re-authenticating."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    auth_client.user = SECOND_MOCKED_USER
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: MOCKED_EMAIL,
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


async def test_form_unique_id_already_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that setting up a config with a unique ID that already exists fails."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: MOCKED_EMAIL,
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error_type", "error_string"),
    [
        (AuthFailedError, "invalid_auth"),
        (CyncError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_two_factor_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    auth_client: MagicMock,
    error_type: Exception,
    error_string: str,
) -> None:
    """Test we handle a request for a two factor code with errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    auth_client.login.side_effect = TwoFactorRequiredError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: MOCKED_EMAIL,
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "two_factor"

    # Enter two factor code
    auth_client.login.side_effect = error_type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TWO_FACTOR_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_string}
    assert result["step_id"] == "user"

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    auth_client.login.side_effect = TwoFactorRequiredError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: MOCKED_EMAIL,
            CONF_PASSWORD: "test-password",
        },
    )

    # Enter two factor code
    auth_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_TWO_FACTOR_CODE: "567890",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCKED_EMAIL
    assert result["data"] == {
        CONF_USER_ID: MOCKED_USER.user_id,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: ANY,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert result["result"].unique_id == str(MOCKED_USER.user_id)
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error_type", "error_string"),
    [
        (AuthFailedError, "invalid_auth"),
        (CyncError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    auth_client: MagicMock,
    error_type: Exception,
    error_string: str,
) -> None:
    """Test we handle errors in the user step of the setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    auth_client.login.side_effect = error_type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: MOCKED_EMAIL,
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_string}
    assert result["step_id"] == "user"

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    auth_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: MOCKED_EMAIL,
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCKED_EMAIL
    assert result["data"] == {
        CONF_USER_ID: MOCKED_USER.user_id,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: ANY,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert result["result"].unique_id == str(MOCKED_USER.user_id)
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("error_type", "error_string"),
    [
        (AuthFailedError, "invalid_auth"),
        (CyncError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    auth_client: MagicMock,
    error_type: Exception,
    error_string: str,
) -> None:
    """Test we handle errors in the reauth flow."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    auth_client.login.side_effect = error_type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: MOCKED_EMAIL,
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_string}
    assert result["step_id"] == "reauth_confirm"

    # Make sure the config flow tests finish with FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    auth_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: MOCKED_EMAIL,
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_USER_ID: MOCKED_USER.user_id,
        CONF_AUTHORIZE_STRING: "test_authorize_string",
        CONF_EXPIRES_AT: ANY,
        CONF_ACCESS_TOKEN: "test_token",
        CONF_REFRESH_TOKEN: "test_refresh_token",
    }
    assert len(mock_setup_entry.mock_calls) == 1
