"""Tests for Xthings Cloud config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.xthings_cloud.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from ha_xthings_cloud import XthingsCloudApiError, XthingsCloudAuthError

from tests.common import MockConfigEntry

MOCK_EMAIL = "test@example.com"
MOCK_PASSWORD = "testpassword"
MOCK_TOKEN = "mock_token"
MOCK_REFRESH_TOKEN = "mock_refresh"


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
) -> None:
    """Test successful user login flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_EMAIL
    assert result["data"][CONF_EMAIL] == MOCK_EMAIL
    assert result["data"][CONF_TOKEN] == MOCK_TOKEN


async def test_user_flow_auth_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
) -> None:
    """Test user flow with auth error."""
    mock_api_client.async_login.side_effect = XthingsCloudAuthError(
        "Auth failed", code=21014
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "password_wrong"


async def test_user_flow_api_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
) -> None:
    """Test user flow with API error."""
    mock_api_client.async_login.side_effect = XthingsCloudApiError(
        "API error", code=22001
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "device_not_found"


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
) -> None:
    """Test user flow with connection error (code=0)."""
    mock_api_client.async_login.side_effect = XthingsCloudApiError(
        "Connection failed", code=0
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_unknown_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
) -> None:
    """Test user flow with unexpected exception."""
    mock_api_client.async_login.side_effect = RuntimeError("unexpected")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user flow aborts if already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_2fa_email(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_login_success: dict,
    mock_login_2fa_email: dict,
) -> None:
    """Test user flow with 2FA email verification."""
    mock_api_client.async_login.return_value = mock_login_2fa_email
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "2fa_email"

    # Submit verification code
    mock_api_client.async_login.return_value = mock_login_success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"verification_code": "123456"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_EMAIL


async def test_user_flow_2fa_phone(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_login_success: dict,
    mock_login_2fa_phone: dict,
) -> None:
    """Test user flow with 2FA phone verification."""
    mock_api_client.async_login.return_value = mock_login_2fa_phone
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "2fa_phone"

    mock_api_client.async_login.return_value = mock_login_success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"verification_code": "123456"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_2fa_auth_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_login_2fa_email: dict,
) -> None:
    """Test 2FA step with auth error."""
    mock_api_client.async_login.return_value = mock_login_2fa_email
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["step_id"] == "2fa_email"

    mock_api_client.async_login.side_effect = XthingsCloudAuthError(
        "Bad code", code=21005
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"verification_code": "000000"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "email_verify_error"


async def test_2fa_invalid_code_returns_2fa(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_login_2fa_email: dict,
) -> None:
    """Test 2FA step when server returns 2fa again (invalid code)."""
    mock_api_client.async_login.return_value = mock_login_2fa_email
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    # Server returns 2fa again = invalid code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"verification_code": "000000"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_verification_code"


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow success."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_auth_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with auth error."""
    mock_config_entry.add_to_hass(hass)
    mock_api_client.async_login.side_effect = XthingsCloudAuthError(
        "Auth failed", code=21014
    )
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "password_wrong"


async def test_reauth_flow_2fa_email(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_config_entry: MockConfigEntry,
    mock_login_success: dict,
    mock_login_2fa_email: dict,
) -> None:
    """Test reauth flow with 2FA email."""
    mock_config_entry.add_to_hass(hass)
    mock_api_client.async_login.return_value = mock_login_2fa_email
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_2fa_email"

    mock_api_client.async_login.return_value = mock_login_success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"verification_code": "123456"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_2fa_phone(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_config_entry: MockConfigEntry,
    mock_login_success: dict,
    mock_login_2fa_phone: dict,
) -> None:
    """Test reauth flow with 2FA phone."""
    mock_config_entry.add_to_hass(hass)
    mock_api_client.async_login.return_value = mock_login_2fa_phone
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_2fa_phone"

    mock_api_client.async_login.return_value = mock_login_success
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"verification_code": "123456"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_unknown_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with unexpected error."""
    mock_config_entry.add_to_hass(hass)
    mock_api_client.async_login.side_effect = RuntimeError("unexpected")
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_2fa_api_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_login_2fa_email: dict,
) -> None:
    """Test 2FA step with API error."""
    mock_api_client.async_login.return_value = mock_login_2fa_email
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )

    mock_api_client.async_login.side_effect = XthingsCloudApiError(
        "API error", code=0
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"verification_code": "123456"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_2fa_unknown_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_instance_id: None,
    mock_login_2fa_email: dict,
) -> None:
    """Test 2FA step with unexpected error."""
    mock_api_client.async_login.return_value = mock_login_2fa_email
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )

    mock_api_client.async_login.side_effect = RuntimeError("unexpected")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"verification_code": "123456"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"
