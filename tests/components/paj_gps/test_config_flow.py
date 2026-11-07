"""Tests for the PAJ GPS config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pajgps_api.models.auth import AuthResponse
from pajgps_api.pajgps_api_error import (
    AuthenticationError,
    RequestError,
    TokenRefreshError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.paj_gps.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

VALID_USER_INPUT = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "s3cr3t",
}


@pytest.mark.parametrize(
    ("raw_email", "expected_email"),
    [
        ("user@example.com", "user@example.com"),
        ("  USER@EXAMPLE.COM  ", "user@example.com"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_user_flow(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    raw_email: str,
    expected_email: str,
) -> None:
    """Full user flow must show a form then create an entry with normalized data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: raw_email, CONF_PASSWORD: "s3cr3t"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_email
    assert result["data"][CONF_EMAIL] == expected_email
    assert result["data"][CONF_PASSWORD] == "s3cr3t"
    assert result["result"].unique_id == "42"


async def test_duplicate_email_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_paj_gps_api: AsyncMock,
) -> None:
    """A flow for an already-configured account must abort with already_configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_USER_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (AuthenticationError("bad creds"), "invalid_auth"),
        (TokenRefreshError("refresh failed"), "invalid_auth"),
        (RequestError("Service unavailable"), "cannot_connect"),
        (ConnectionError("timeout"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_invalid_credentials_shows_form_error(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Credential errors must re-show the form with the correct error key."""
    mock_paj_gps_api.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_paj_gps_api.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_paj_gps_api: AsyncMock,
) -> None:
    """Reauth must update the password and keep the email."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"][CONF_EMAIL] == "test@example.com"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new_secret"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "new_secret",
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(
            AuthenticationError("bad creds"), "invalid_auth", id="invalid_auth"
        ),
        pytest.param(
            TokenRefreshError("refresh failed"), "invalid_auth", id="token_refresh"
        ),
        pytest.param(
            RequestError("Service unavailable"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(ConnectionError("timeout"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_paj_gps_api: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Reauth errors must re-show the form and allow recovery."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_paj_gps_api.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new_secret"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}

    mock_paj_gps_api.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new_secret"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_secret"


async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_paj_gps_api: AsyncMock,
) -> None:
    """Reauth with credentials of a different account must abort."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_paj_gps_api.login.return_value = AuthResponse(
        userID=99, token="other_token", refresh_token="other_refresh"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new_secret"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_PASSWORD] == "secret"
