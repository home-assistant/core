"""Tests for the Level Lock config flow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.components.levelhome.config_flow import OAuth2FlowHandler
from homeassistant.components.levelhome.const import (
    CONF_OAUTH2_BASE_URL,
    CONF_PARTNER_BASE_URL,
    DEFAULT_OAUTH2_BASE_URL,
    DEFAULT_PARTNER_BASE_URL,
    DOMAIN,
    OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH,
    OAUTH2_OTP_CONFIRM_PATH,
    OAUTH2_TOKEN_EXCHANGE_PATH,
    PARTNER_OTP_START_PATH,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.usefixtures("mock_oauth_patches", "mock_oauth_responses")
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test the full happy path of the OTP-enhanced OAuth2 config flow."""
    # Begin flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit user_id (use defaults for base URLs)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"user_id": "test-user"}
    )
    # Next step should prompt for OTP
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "otp"

    # Submit OTP code (in ABCD-1234 format)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"code": "ABCD-1234"}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Level Lock"
    # Entry data contains the token and implementation domain
    assert result["data"]["auth_implementation"] == DOMAIN
    token = result["data"]["token"]
    assert token["access_token"] == "at"
    assert token["refresh_token"] == "rt"
    assert token["token_type"].lower() == "bearer"
    assert isinstance(token["expires_in"], int)
    assert "expires_at" in token
    # Options store selected base URLs
    assert result["options"][CONF_OAUTH2_BASE_URL] == DEFAULT_OAUTH2_BASE_URL
    assert result["options"][CONF_PARTNER_BASE_URL] == DEFAULT_PARTNER_BASE_URL


@pytest.mark.usefixtures("mock_oauth_patches")
async def test_otp_invalid_code_shows_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """OTP errors should keep user on the OTP step with an error."""
    aioclient_mock.get(
        "https://oauth.example/authorize",
        text='<input type="hidden" name="request_uuid" value="req-123">',
    )
    aioclient_mock.post(
        f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"user_id": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "otp"

    # Invalid OTP should set errors["base"] = "invalid_auth"
    aioclient_mock.post(
        f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=400
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"code": "ABCD-1234"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_missing_implementation_missing_configuration(
    hass: HomeAssistant,
) -> None:
    """Abort with missing_configuration when no implementation and no app creds."""

    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_application_credentials",
            return_value={},
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Submit user to reach start step that checks implementations
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "missing_configuration"


async def test_missing_implementation_missing_credentials(
    hass: HomeAssistant,
) -> None:
    """Abort with missing_credentials when app creds exist but no impl."""

    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_application_credentials",
            return_value={DOMAIN: object()},
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "missing_credentials"


async def test_authorize_url_generation_error(hass: HomeAssistant) -> None:
    """Abort when authorize URL cannot be generated."""

    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="ruri",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            side_effect=Exception("boom"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "authorize_url_timeout"


async def test_authorize_request_4xx(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Abort when GET authorize returns 4xx."""

    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="ruri",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get("https://oauth.example/authorize", status=400)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_failed"


async def test_missing_request_uuid_in_html(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Abort when authorize HTML lacks request_uuid input."""

    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="ruri",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get("https://oauth.example/authorize", text="<html></html>")
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_error"


async def test_otp_start_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Abort when partner OTP start fails."""

    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="ruri",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req-1">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=400
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_failed"


async def test_grant_permissions_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Abort when grant permissions fails."""

    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="https://r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req-1">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            status=400,
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        # move to otp
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_failed"


async def test_missing_redirect_uri_after_grant(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Abort when grant returns no redirect_uri."""

    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="https://r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req-1">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            json={},
            status=200,
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_error"


async def test_missing_code_in_redirect_uri(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Abort when redirect_uri has no code param."""

    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="https://r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req-1">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            json={"redirect_uri": "https://example.com/redirect"},
            status=200,
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_error"


async def test_token_exchange_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Abort when token exchange fails."""

    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="https://r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req-1">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            json={"redirect_uri": "https://example.com/redirect?code=abc"},
            status=200,
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}", status=400
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_failed"


async def test_token_exchange_bad_expires_in(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Abort when expires_in cannot be converted to int."""

    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="https://r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req-1">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            json={"redirect_uri": "https://example.com/redirect?code=abc"},
            status=200,
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}",
            json={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": "bad",
                "token_type": "Bearer",
            },
            status=200,
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_error"


async def test_reauth_paths(hass: HomeAssistant) -> None:
    """Test reauth steps show confirm and then return to user."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "at",
                "refresh_token": "rt",
                "expires_at": 9999999999,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        },
        unique_id="uid-re",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_grant_permissions_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Grant permissions raises ClientError -> oauth_failed."""
    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            exc=ClientError(),
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_failed"


async def test_reauth_full_success_updates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Reauth completes and updates existing entry (covers reauth update branch)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old",
                "refresh_token": "old-rt",
                "expires_at": 1,
                "expires_in": 1,
                "token_type": "Bearer",
            },
        },
        unique_id="uid-re2",
    )
    entry.add_to_hass(hass)

    impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            json={"redirect_uri": "https://cb?code=abc"},
            status=200,
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}",
            json={
                "access_token": "new",
                "refresh_token": "new-rt",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            status=200,
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
        )
        # confirm
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        # user step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        # otp step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        # Should abort to update existing entry
        assert result["type"] == FlowResultType.ABORT


async def test_authorize_request_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Authorize GET raises ClientError -> oauth_failed."""
    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get("https://oauth.example/authorize", exc=ClientError())
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_failed"


async def test_otp_start_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Partner OTP start raises ClientError -> oauth_failed."""
    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", exc=ClientError()
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_failed"


async def test_otp_confirm_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """OTP confirm raises ClientError -> invalid_auth error on form."""
    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", exc=ClientError()
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "otp"
        assert result["errors"] == {"base": "invalid_auth"}


class _PkceNotSupportedError(Exception):
    """Exception raised when PKCE is not supported."""


class _ImplRaises:
    domain = DOMAIN
    name = "Level Lock"
    client_id = "id"
    redirect_uri = "r"

    @property
    def extra_token_resolve_data(self):
        raise _PkceNotSupportedError("boom")


async def test_extra_token_resolve_data_raises(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Ignore errors when accessing extra_token_resolve_data."""
    impl = _ImplRaises()
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            json={"redirect_uri": "https://cb?code=abc"},
            status=200,
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}",
            json={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            status=200,
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_client_secret_included(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Handle flow when implementation provides a client_secret."""
    impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="r",
        extra_token_resolve_data={},
        client_secret="s",
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            json={"redirect_uri": "https://cb?code=abc"},
            status=200,
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}",
            json={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            status=200,
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_token_exchange_client_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Token exchange raises ClientError -> oauth_failed."""
    impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            json={"redirect_uri": "https://cb?code=abc"},
            status=200,
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}", exc=ClientError()
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_failed"


async def test_token_missing_expires_in(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Abort when token lacks expires_in."""
    impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="id",
        redirect_uri="r",
        extra_token_resolve_data={},
    )
    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            json={"redirect_uri": "https://cb?code=abc"},
            status=200,
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}",
            json={"access_token": "at", "refresh_token": "rt", "token_type": "Bearer"},
            status=200,
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "u"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCD-1234"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "oauth_error"


def test_extra_authorize_data_property() -> None:
    """Directly verify extra_authorize_data returns expected scope."""
    handler = object.__new__(OAuth2FlowHandler)
    assert handler.extra_authorize_data == {"scope": "all"}


async def test_otp_code_format_validation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test OTP code format validation and auto-formatting."""
    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="client-123",
        redirect_uri="https://example.com/redirect",
        extra_token_resolve_data={},
    )

    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req-123">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "test-user"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "otp"

        # Test invalid format: too short
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABC123"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "otp"
        assert result["errors"] == {"code": "invalid_code_format"}

        # Test invalid format: wrong pattern (numbers first)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "1234ABCD"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "otp"
        assert result["errors"] == {"code": "invalid_code_format"}

        # Test invalid format: all letters
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "ABCDEFGH"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "otp"
        assert result["errors"] == {"code": "invalid_code_format"}

        # Mock successful OTP validation for valid formats
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            json={"redirect_uri": "https://example.com/redirect?code=authcode-xyz"},
            status=200,
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}",
            json={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            status=200,
        )

        # Test valid format: lowercase letters auto-capitalized, no dash
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "abcd1234"}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_otp_code_with_dash_accepted(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that OTP code with dash is accepted and preserved."""
    fake_impl = SimpleNamespace(
        domain=DOMAIN,
        name="Level Lock",
        client_id="client-123",
        redirect_uri="https://example.com/redirect",
        extra_token_resolve_data={},
    )

    with (
        patch(
            "homeassistant.components.levelhome.config_flow.config_entry_oauth2_flow.async_get_implementations",
            return_value={"impl": fake_impl},
        ),
        patch(
            "homeassistant.components.levelhome.config_flow.OAuth2FlowHandler.async_generate_authorize_url",
            return_value="https://oauth.example/authorize",
        ),
    ):
        aioclient_mock.get(
            "https://oauth.example/authorize",
            text='<input type="hidden" name="request_uuid" value="req-123">',
        )
        aioclient_mock.post(
            f"{DEFAULT_PARTNER_BASE_URL}{PARTNER_OTP_START_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_OTP_CONFIRM_PATH}", status=200
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH}",
            json={"redirect_uri": "https://example.com/redirect?code=authcode-xyz"},
            status=200,
        )
        aioclient_mock.post(
            f"{DEFAULT_OAUTH2_BASE_URL}{OAUTH2_TOKEN_EXCHANGE_PATH}",
            json={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            status=200,
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"user_id": "test-user"}
        )

        # Test valid format with dash already present
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "WXYZ-5678"}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
