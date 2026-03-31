"""Tests for the PAJ GPS config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pajgps_api.pajgps_api_error import AuthenticationError, TokenRefreshError

from homeassistant.components.paj_gps.config_flow import _validate_credentials
from homeassistant.components.paj_gps.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VALID_USER_INPUT = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "s3cr3t",
}


async def test_no_input_returns_form(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
) -> None:
    """Calling async_step_user() with no input must return a form with step_id 'user'."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_valid_input_creates_entry(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
) -> None:
    """Valid input must create an entry with the email as title and correct data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == VALID_USER_INPUT[CONF_EMAIL]
    assert result["data"][CONF_EMAIL] == VALID_USER_INPUT[CONF_EMAIL]
    assert result["data"][CONF_PASSWORD] == VALID_USER_INPUT[CONF_PASSWORD]


async def test_duplicate_email_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_paj_gps_api: AsyncMock,
) -> None:
    """A flow with an already-configured email must abort with already_configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EMAIL: "test@example.com",  # same as mock_config_entry
            CONF_PASSWORD: "secret",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_credentials_shows_form_error(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
) -> None:
    """Authentication failure must re-show the form with an error."""
    mock_paj_gps_api.login.side_effect = AuthenticationError("bad creds")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


# ---------------------------------------------------------------------------
# _validate_credentials unit tests
# ---------------------------------------------------------------------------


async def test_validate_credentials_returns_none_on_success(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
) -> None:
    """A successful login must return None (no error)."""
    result = await _validate_credentials("user@example.com", "secret", hass)
    assert result is None


async def test_validate_credentials_returns_invalid_auth_on_authentication_error(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
) -> None:
    """AuthenticationError from login() must map to 'invalid_auth'."""
    mock_paj_gps_api.login.side_effect = AuthenticationError("bad creds")
    result = await _validate_credentials("user@example.com", "wrong", hass)
    assert result == "invalid_auth"


async def test_validate_credentials_returns_invalid_auth_on_token_refresh_error(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
) -> None:
    """TokenRefreshError from login() must map to 'invalid_auth'."""
    mock_paj_gps_api.login.side_effect = TokenRefreshError("refresh failed")
    result = await _validate_credentials("user@example.com", "secret", hass)
    assert result == "invalid_auth"


async def test_validate_credentials_returns_unknown_on_generic_exception(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
) -> None:
    """Any unexpected exception from login() must map to 'unknown'."""
    mock_paj_gps_api.login.side_effect = ConnectionError("timeout")
    result = await _validate_credentials("user@example.com", "secret", hass)
    assert result == "unknown"
