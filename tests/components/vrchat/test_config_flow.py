"""Test the VRChat config flow."""

from unittest.mock import AsyncMock, PropertyMock, patch

from aiohttp import ClientConnectionError
import pytest
import vrchatapi
from vrchatapi.highlevel import TwoFactorAuthChallenge, TwoFactorAuthRequired

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
            vrchatapi.exceptions.UnauthorizedException(status=401),
            "invalid_auth",
            id="missing_reason",
        ),
        pytest.param(
            vrchatapi.exceptions.UnauthorizedException(
                status=401, reason="Email 2 Factor Authentication"
            ),
            "invalid_auth",
            id="untyped_challenge_message",
        ),
        pytest.param(
            vrchatapi.exceptions.ApiException(status=500, reason="Server error"),
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            ClientConnectionError("Connection failed"),
            "cannot_connect",
            id="connection_error",
        ),
        pytest.param(TimeoutError(), "cannot_connect", id="timeout"),
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
    unauthorized = TwoFactorAuthRequired(TwoFactorAuthChallenge.TOTP)
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
    unauthorized = TwoFactorAuthRequired(TwoFactorAuthChallenge.EMAIL_OTP)
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
    unauthorized = TwoFactorAuthRequired(TwoFactorAuthChallenge.TOTP)
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
    ("step_id", "verification_method", "verification_key", "challenge"),
    [
        pytest.param(
            "2fa",
            "verify2_fa",
            CONF_2FA_CODE,
            TwoFactorAuthChallenge.TOTP,
            id="authenticator_app",
        ),
        pytest.param(
            "email_2fa",
            "verify2_fa_email_code",
            CONF_EMAIL_2FA_CODE,
            TwoFactorAuthChallenge.EMAIL_OTP,
            id="email",
        ),
    ],
)
@pytest.mark.parametrize(
    ("verification_results", "user_results", "error"),
    [
        pytest.param(
            [vrchatapi.exceptions.BadRequestException(status=400), None],
            [MOCK_USER],
            "invalid_auth",
            id="invalid_code_bad_request",
        ),
        pytest.param(
            [None, None],
            [vrchatapi.exceptions.BadRequestException(status=400), MOCK_USER],
            "cannot_connect",
            id="current_user_bad_request",
        ),
        pytest.param(
            [vrchatapi.exceptions.UnauthorizedException(status=401), None],
            [MOCK_USER],
            "invalid_auth",
            id="invalid_code",
        ),
        pytest.param(
            [vrchatapi.exceptions.ServiceException(status=500), None],
            [MOCK_USER],
            "cannot_connect",
            id="server_error",
        ),
        pytest.param(
            [vrchatapi.exceptions.ApiException(status=429), None],
            [MOCK_USER],
            "cannot_connect",
            id="rate_limit",
        ),
        pytest.param(
            [ClientConnectionError(), None],
            [MOCK_USER],
            "cannot_connect",
            id="connection_error",
        ),
        pytest.param(
            [TimeoutError(), None],
            [MOCK_USER],
            "cannot_connect",
            id="timeout",
        ),
        pytest.param(
            [None, None],
            [vrchatapi.exceptions.ServiceException(status=500), MOCK_USER],
            "cannot_connect",
            id="current_user_server_error",
        ),
    ],
)
async def test_two_factor_error(
    hass: HomeAssistant,
    step_id: str,
    verification_method: str,
    verification_key: str,
    challenge: TwoFactorAuthChallenge,
    verification_results: list[Exception | None],
    user_results: list[Exception | dict[str, str]],
    error: str,
) -> None:
    """Test two-factor errors preserve the flow and allow a successful retry."""
    unauthorized = TwoFactorAuthRequired(challenge)
    with (
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.get_current_user",
            new=AsyncMock(side_effect=[unauthorized, *user_results]),
        ),
        patch(
            "homeassistant.components.vrchat.config_flow.VRChatAPI.close",
            new=AsyncMock(),
        ) as mock_close,
        patch(
            f"homeassistant.components.vrchat.config_flow.VRChatAPI.{verification_method}",
            new=AsyncMock(side_effect=verification_results),
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
        assert result["errors"] == {"base": error}
        mock_close.assert_not_awaited()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {verification_key: "123456"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_USER["id"]
    mock_close.assert_awaited_once()
