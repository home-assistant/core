"""Test the VRChat config flow."""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
import vrchatapi

from homeassistant import config_entries
from homeassistant.components.vrchat.const import (
    CONF_2FA_CODE,
    CONF_EMAIL_2FA_CODE,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_USER = {"id": "usr_123", "username": "vrchat_user"}
USER_INPUT = {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "password"}


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the credential flow."""
    with (
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.get_current_user",
            new=AsyncMock(return_value=MOCK_USER),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.cookie",
            new_callable=PropertyMock,
            return_value={},
        ),
        patch(
            "homeassistant.components.vrchat.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.close",
            new=AsyncMock(),
        ) as mock_close,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "vrchat_user"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "usr_123"
    mock_close.assert_awaited_once()


async def test_user_flow_duplicate_account(hass: HomeAssistant) -> None:
    """Test that an existing account cannot be added twice."""
    MockConfigEntry(domain=DOMAIN, unique_id="usr_123").add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.get_current_user",
            new=AsyncMock(return_value=MOCK_USER),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.cookie",
            new_callable=PropertyMock,
            return_value={},
        ),
        patch(
            "homeassistant.components.vrchat.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.close",
            new=AsyncMock(),
        ) as mock_close,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_close.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(
            vrchatapi.exceptions.UnauthorizedException(
                status=401, reason="Invalid credentials"
            ),
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            vrchatapi.exceptions.ApiException(status=500, reason="Server error"),
            "cannot_connect",
            id="cannot_connect",
        ),
    ],
)
async def test_user_flow_error(
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    """Test that the credential form can recover from an error."""
    with (
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.get_current_user",
            new=AsyncMock(side_effect=exception),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.close",
            new=AsyncMock(),
        ) as mock_close,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}
    mock_close.assert_awaited_once()


async def test_authenticator_two_factor_flow(hass: HomeAssistant) -> None:
    """Test authenticator-app two-factor authentication."""
    unauthorized = vrchatapi.exceptions.UnauthorizedException(
        status=200, reason="2 Factor Authentication"
    )
    with (
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.get_current_user",
            new=AsyncMock(side_effect=[unauthorized, MOCK_USER]),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.verify2_fa",
            new=AsyncMock(),
        ) as mock_verify,
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.cookie",
            new_callable=PropertyMock,
            return_value={},
        ),
        patch(
            "homeassistant.components.vrchat.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.close",
            new=AsyncMock(),
        ) as mock_close,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        assert result["step_id"] == "2fa"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_2FA_CODE: "123456"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_verify.assert_awaited_once_with("123456")
    mock_close.assert_awaited_once()


async def test_email_two_factor_flow(hass: HomeAssistant) -> None:
    """Test email two-factor authentication."""
    unauthorized = vrchatapi.exceptions.UnauthorizedException(
        status=200, reason="Email 2 Factor Authentication"
    )
    with (
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.get_current_user",
            new=AsyncMock(side_effect=[unauthorized, MOCK_USER]),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.verify2_fa_email_code",
            new=AsyncMock(),
        ) as mock_verify,
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.cookie",
            new_callable=PropertyMock,
            return_value={},
        ),
        patch(
            "homeassistant.components.vrchat.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.close",
            new=AsyncMock(),
        ) as mock_close,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        assert result["step_id"] == "email_2fa"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL_2FA_CODE: "123456"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_verify.assert_awaited_once_with("123456")
    mock_close.assert_awaited_once()


async def test_cancel_two_factor_flow_closes_api(hass: HomeAssistant) -> None:
    """Test that cancelling a two-factor flow closes its API client."""
    unauthorized = vrchatapi.exceptions.UnauthorizedException(
        status=200, reason="2 Factor Authentication"
    )
    with (
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.get_current_user",
            new=AsyncMock(side_effect=unauthorized),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.close",
            new=AsyncMock(),
        ) as mock_close,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        assert result["step_id"] == "2fa"
        hass.config_entries.flow.async_abort(result["flow_id"])
        await hass.async_block_till_done()

    mock_close.assert_awaited_once()


@pytest.mark.parametrize(
    ("step_id", "verification_method", "verification_key", "reason"),
    [
        pytest.param(
            "2fa",
            "verify2_fa",
            CONF_2FA_CODE,
            "2 Factor Authentication",
            id="authenticator_app",
        ),
        pytest.param(
            "email_2fa",
            "verify2_fa_email_code",
            CONF_EMAIL_2FA_CODE,
            "Email 2 Factor Authentication",
            id="email",
        ),
    ],
)
async def test_two_factor_error(
    hass: HomeAssistant,
    step_id: str,
    verification_method: str,
    verification_key: str,
    reason: str,
) -> None:
    """Test that a failed two-factor code returns to the same form."""
    unauthorized = vrchatapi.exceptions.UnauthorizedException(status=200, reason=reason)
    with (
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.get_current_user",
            new=AsyncMock(side_effect=unauthorized),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.close",
            new=AsyncMock(),
        ) as mock_close,
        patch(
            f"homeassistant.components.vrchat.config_flow.VRChatAPI.{verification_method}",
            new=AsyncMock(
                side_effect=vrchatapi.exceptions.ApiException(
                    status=401, reason="Invalid code"
                )
            ),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        assert result["step_id"] == step_id
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {verification_key: "123456"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id
    assert result["errors"] == {"base": "invalid_auth"}
    mock_close.assert_not_awaited()
