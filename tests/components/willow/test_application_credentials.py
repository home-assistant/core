"""Tests for the Willow application credentials platform."""

import pytest

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.willow.application_credentials import (
    DEFAULT_EXPIRES_IN,
    WillowOAuth2Implementation,
    async_get_auth_implementation,
)
from homeassistant.components.willow.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def implementation(hass: HomeAssistant) -> WillowOAuth2Implementation:
    """Return a Willow OAuth2 implementation."""
    return WillowOAuth2Implementation(
        hass,
        DOMAIN,
        "client-id",
        "client-secret",
        "https://example.test/authorize",
        OAUTH2_TOKEN,
    )


async def test_async_get_auth_implementation(hass: HomeAssistant) -> None:
    """The platform returns a Willow OAuth2 implementation."""
    implementation = await async_get_auth_implementation(
        hass, DOMAIN, ClientCredential("client-id", "client-secret")
    )
    assert isinstance(implementation, WillowOAuth2Implementation)


async def test_resolve_external_data_adds_default_expiry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    implementation: WillowOAuth2Implementation,
) -> None:
    """A token without expires_in is normalized to the long-lived default."""
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={"access_token": "abc", "refresh_token": "def"},
    )

    token = await implementation.async_resolve_external_data(
        {"code": "code", "state": {"redirect_uri": "https://example.test/cb"}}
    )

    assert token["expires_in"] == DEFAULT_EXPIRES_IN


async def test_resolve_external_data_keeps_provided_expiry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    implementation: WillowOAuth2Implementation,
) -> None:
    """A token that already has expires_in is left untouched."""
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={"access_token": "abc", "refresh_token": "def", "expires_in": 60},
    )

    token = await implementation.async_resolve_external_data(
        {"code": "code", "state": {"redirect_uri": "https://example.test/cb"}}
    )

    assert token["expires_in"] == 60


async def test_refresh_token_without_refresh_token_is_noop(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    implementation: WillowOAuth2Implementation,
) -> None:
    """Refreshing a token that has no refresh_token returns it unchanged."""
    token = {"access_token": "abc"}

    assert await implementation._async_refresh_token(token) is token
    assert len(aioclient_mock.mock_calls) == 0


async def test_refresh_token_normalizes_expiry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    implementation: WillowOAuth2Implementation,
) -> None:
    """A refreshed token without expires_in is normalized."""
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={"access_token": "new", "refresh_token": "keep"},
    )

    token = await implementation._async_refresh_token({"refresh_token": "old"})

    assert token["access_token"] == "new"
    assert token["expires_in"] == DEFAULT_EXPIRES_IN
