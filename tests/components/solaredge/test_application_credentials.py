"""SolarEdge OAuth contract tests using synthetic credentials and responses."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from yarl import URL

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.solaredge.application_credentials import (
    TOKEN_URL,
    async_get_auth_implementation,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError


async def test_json_exchange_and_refresh(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Both requests must use JSON and retain the rotated refresh token."""
    implementation = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic-client", "synthetic-secret")
    )
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-refresh",
            "expires_in": 7200,
            "token_type": "Bearer",
        },
    )
    with patch(
        "homeassistant.components.solaredge.application_credentials.async_get_clientsession",
        wraps=async_get_clientsession,
    ) as get_session:
        session = get_session(hass)
        with patch.object(session, "post", wraps=session.post) as post:
            result = await implementation.async_resolve_external_data(
                {
                    "code": "synthetic-code",
                    "state": {"redirect_uri": "https://example.com/callback"},
                }
            )
            assert "json" in post.call_args.kwargs
            assert "data" not in post.call_args.kwargs
            assert post.call_args.kwargs["allow_redirects"] is False
    assert result["refresh_token"] == "synthetic-refresh"
    body = aioclient_mock.mock_calls[0][2]
    assert body["grant_type"] == "authorization_code"
    assert body["redirect_uri"] == "https://example.com/callback"
    assert body["client_id"] == "synthetic-client"
    assert body["client_secret"] == "synthetic-secret"
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "synthetic-access-2",
            "refresh_token": "synthetic-refresh-2",
            "expires_in": 7200,
            "token_type": "Bearer",
        },
    )
    result = await implementation.async_refresh_token(result)
    assert result["refresh_token"] == "synthetic-refresh-2"
    assert aioclient_mock.mock_calls[0][2]["grant_type"] == "refresh_token"
    assert aioclient_mock.mock_calls[0][2]["refresh_token"] == "synthetic-refresh"


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (400, OAuth2TokenRequestReauthError),
        (401, OAuth2TokenRequestReauthError),
        (429, OAuth2TokenRequestTransientError),
        (503, OAuth2TokenRequestTransientError),
        (302, OAuth2TokenRequestConnectionError),
    ],
)
async def test_token_errors_redacted(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    error: type[Exception],
) -> None:
    """Do not forward potentially secret-bearing provider error bodies."""
    implementation = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic-client", "synthetic-secret")
    )
    aioclient_mock.post(TOKEN_URL, status=status, text="synthetic-secret-echo")
    with pytest.raises(error) as err:
        await implementation.async_refresh_token({"refresh_token": "synthetic-refresh"})
    assert "synthetic-secret" not in str(err.value)
    assert aioclient_mock.call_count == 1


async def test_authorize_preserves_signed_state_and_generated_redirect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Never work around a provider by removing HA's CSRF state."""
    implementation = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic-client", "synthetic-secret")
    )
    hass.config.components.add("my")
    hass.config.external_url = "https://example.com"
    url = URL(await implementation.async_generate_authorize_url("synthetic-flow"))
    assert url.host == "connect.solaredge.com"
    assert (
        url.query["redirect_uri"]
        == "https://example.com/auth/external/callback/solaredge"
    )
    assert url.query["external_id"] == url.query["state"]
    state = config_entry_oauth2_flow._decode_jwt(hass, url.query["state"])
    assert state["flow_id"] == "synthetic-flow"
    assert state["redirect_uri"] == url.query["redirect_uri"]
    assert state["exp"] > 0
    assert state["nonce"]
    assert url.query["scope"] == "SITE_DATA DEVICE_DATA"
    assert "synthetic-secret" not in str(url)
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-refresh",
            "expires_in": 7200,
            "token_type": "Bearer",
        },
    )
    await implementation.async_resolve_external_data(
        {"code": "synthetic-code", "state": state}
    )
    assert aioclient_mock.mock_calls[0][2]["redirect_uri"] == url.query["redirect_uri"]
    assert (
        config_entry_oauth2_flow._decode_jwt(hass, url.query["state"] + "tampered")
        is None
    )


async def test_refresh_serialized_and_persisted(hass: HomeAssistant) -> None:
    """Concurrent reads must not consume the one-use refresh token twice."""
    entry = MockConfigEntry(
        domain="solaredge",
        data={
            "token": {
                "access_token": "synthetic-access",
                "refresh_token": "synthetic-refresh",
                "expires_at": 0,
            }
        },
    )
    entry.add_to_hass(hass)
    implementation = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic-client", "synthetic-secret")
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    with patch.object(
        implementation,
        "async_refresh_token",
        new=AsyncMock(
            return_value={
                "access_token": "synthetic-access-2",
                "refresh_token": "synthetic-refresh-2",
                "expires_at": 9999999999,
            }
        ),
    ) as refresh:
        await asyncio.gather(
            session.async_ensure_token_valid(), session.async_ensure_token_valid()
        )
        refresh.assert_awaited_once()
    assert entry.data["token"]["refresh_token"] == "synthetic-refresh-2"


@pytest.mark.parametrize("external_url", [None, "http://example.com"])
async def test_direct_callback_does_not_fall_back_to_relay(
    hass: HomeAssistant,
    external_url: str | None,
) -> None:
    """Fail closed when the instance has no eligible HTTPS external URL."""
    hass.config.components.add("my")
    hass.config.external_url = external_url
    implementation = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic-client", "synthetic-secret")
    )
    with pytest.raises(NoURLAvailableError):
        await implementation.async_generate_authorize_url("synthetic-flow")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("access_token", ""),
        ("refresh_token", ""),
        ("expires_in", True),
        ("expires_in", -1),
        ("expires_in", "synthetic-secret-echo"),
        ("token_type", 42),
        ("token_type", "NotBearer"),
    ],
)
async def test_malformed_token_is_not_logged_or_persisted(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    field: str,
    value: object,
) -> None:
    """Reject malformed token responses before generic helpers can log them."""
    implementation = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic-client", "synthetic-secret")
    )
    token = {
        "access_token": "synthetic-access",
        "refresh_token": "synthetic-refresh",
        "expires_in": 7200,
        "token_type": "Bearer",
    }
    token[field] = value
    aioclient_mock.post(TOKEN_URL, json=token)
    with pytest.raises(OAuth2TokenRequestConnectionError):
        await implementation.async_resolve_external_data(
            {
                "code": "synthetic-code",
                "state": {"redirect_uri": "https://example.com/auth/external/callback"},
            }
        )
