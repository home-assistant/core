"""Tests for Garmin Connect config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from ha_garmin import GarminAuthError, GarminMFARequired

from homeassistant import config_entries
from homeassistant.components.garmin_connect.const import (
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_form_login_success(hass: HomeAssistant) -> None:
    """Test successful login without MFA."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_auth_result = MagicMock()
    mock_auth_result.di_token = "token"
    mock_auth_result.di_refresh_token = "refresh_token"
    mock_auth_result.di_client_id = "client_id"

    with (
        patch(
            "homeassistant.components.garmin_connect.config_flow.GarminAuth"
        ) as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.config_flow.GarminClient"
        ) as mock_client_class,
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.di_token = "token"
        mock_auth.di_refresh_token = "refresh_token"
        mock_auth.di_client_id = "client_id"
        mock_auth.refresh_session = AsyncMock()
        mock_auth._token_expires_soon.return_value = False
        mock_auth.login = MagicMock(return_value=mock_auth_result)

        mock_profile = MagicMock()
        mock_profile.profile_id = "test@example.com"
        mock_client_class.return_value.get_user_profile = AsyncMock(
            return_value=mock_profile
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password123",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test@example.com"
    assert result2["data"] == {
        CONF_TOKEN: "token",
        CONF_REFRESH_TOKEN: "refresh_token",
        CONF_CLIENT_ID: "client_id",
    }


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.garmin_connect.config_flow.GarminAuth"
    ) as mock_auth_class:
        mock_auth = mock_auth_class.return_value
        mock_auth.login = MagicMock(side_effect=GarminAuthError("Invalid credentials"))

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_mfa_required(hass: HomeAssistant) -> None:
    """Test MFA flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.garmin_connect.config_flow.GarminAuth"
    ) as mock_auth_class:
        mock_auth = mock_auth_class.return_value
        mock_auth.login = MagicMock(side_effect=GarminMFARequired("mfa_ticket"))

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password123",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "mfa"


async def test_form_mfa_complete(hass: HomeAssistant) -> None:
    """Test completing MFA."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_auth_result = MagicMock()
    mock_auth_result.di_token = "token"
    mock_auth_result.di_refresh_token = "refresh_token"
    mock_auth_result.di_client_id = "client_id"

    with (
        patch(
            "homeassistant.components.garmin_connect.config_flow.GarminAuth"
        ) as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.config_flow.GarminClient"
        ) as mock_client_class,
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.di_token = "token"
        mock_auth.di_refresh_token = "refresh_token"
        mock_auth.di_client_id = "client_id"
        mock_auth.refresh_session = AsyncMock()
        mock_auth._token_expires_soon.return_value = False
        mock_auth.login = MagicMock(side_effect=GarminMFARequired("mfa_ticket"))
        mock_auth.complete_mfa = MagicMock(return_value=mock_auth_result)

        mock_profile = MagicMock()
        mock_profile.profile_id = "test@example.com"
        mock_client_class.return_value.get_user_profile = AsyncMock(
            return_value=mock_profile
        )

        # Step 1: Login triggers MFA
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "password123",
            },
        )
        assert result2["step_id"] == "mfa"

        # Step 2: Complete MFA
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"mfa_code": "123456"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        CONF_TOKEN: "token",
        CONF_REFRESH_TOKEN: "refresh_token",
        CONF_CLIENT_ID: "client_id",
    }
