"""Tests for the Lepro application_credentials module."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components import http
from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.lepro.application_credentials import (
    LoproOAuth2Implementation,
    async_get_auth_implementation,
)
from homeassistant.components.lepro.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import HEADER_FRONTEND_BASE


@pytest.fixture
def impl(hass: HomeAssistant) -> LoproOAuth2Implementation:
    """Return a LoproOAuth2Implementation instance."""
    hass.data[DOMAIN] = {"api_host": "https://api-us-iot.lepro.com"}
    return LoproOAuth2Implementation(
        hass,
        DOMAIN,
        "client-id",
        "client-secret",
        "https://api-us-iot.lepro.com/oauth2/web/login.html",
        "https://api-us-iot.lepro.com/oauth2/token",
    )


async def test_redirect_uri_from_request(
    hass: HomeAssistant,
    impl: LoproOAuth2Implementation,
) -> None:
    """Test that redirect_uri is derived from the current request's frontend base header."""
    mock_request = MagicMock()
    mock_request.headers = {HEADER_FRONTEND_BASE: "https://my.ha.local:8123"}

    token = http.current_request.set(mock_request)
    try:
        uri = impl.redirect_uri
    finally:
        http.current_request.reset(token)

    assert "https://my.ha.local:8123" in uri
    assert "auth/external/callback" in uri


async def test_redirect_uri_fallback(
    hass: HomeAssistant,
    impl: LoproOAuth2Implementation,
) -> None:
    """Test that redirect_uri falls back to the HA helper when no request is active."""
    with patch(
        "homeassistant.components.lepro.application_credentials.config_entry_oauth2_flow.async_get_redirect_uri",
        return_value="https://fallback.example.com/auth/external/callback",
    ):
        uri = impl.redirect_uri

    assert uri == "https://fallback.example.com/auth/external/callback"


async def test_async_resolve_external_data_converts_expires_in(
    hass: HomeAssistant,
    impl: LoproOAuth2Implementation,
) -> None:
    """Test that absolute expires_in timestamps are converted to relative seconds."""
    future_abs = int(time.time()) + 3600
    token = {"access_token": "tok", "expires_in": future_abs}

    with patch.object(
        impl.__class__.__bases__[0],
        "async_resolve_external_data",
        new_callable=AsyncMock,
        return_value=token,
    ):
        result = await impl.async_resolve_external_data({"code": "abc"})

    # Result should be relative, roughly 3600s
    assert 3590 <= result["expires_in"] <= 3600


async def test_async_refresh_token_converts_expires_in(
    hass: HomeAssistant,
    impl: LoproOAuth2Implementation,
) -> None:
    """Test that token refresh converts absolute expires_in to relative seconds."""
    future_abs = int(time.time()) + 7200
    new_token = {
        "access_token": "new-tok",
        "refresh_token": "new-ref",
        "expires_in": future_abs,
    }

    with patch.object(
        impl,
        "_async_refresh_token",
        new_callable=AsyncMock,
        return_value=new_token,
    ):
        result = await impl.async_refresh_token({"refresh_token": "old-ref"})

    assert 7190 <= result["expires_in"] <= 7200
    assert result["expires_at"] == float(future_abs)


async def test_async_refresh_token_no_expires_in(
    hass: HomeAssistant,
    impl: LoproOAuth2Implementation,
) -> None:
    """Test token refresh when server does not return expires_in."""
    new_token = {"access_token": "new-tok", "refresh_token": "new-ref"}

    with patch.object(
        impl,
        "_async_refresh_token",
        new_callable=AsyncMock,
        return_value=new_token,
    ):
        result = await impl.async_refresh_token({"refresh_token": "old-ref"})

    assert result["expires_in"] == 3600
    assert result["expires_at"] > time.time()


async def test_async_get_auth_implementation(hass: HomeAssistant) -> None:
    """Test that async_get_auth_implementation returns a LoproOAuth2Implementation."""
    hass.data[DOMAIN] = {"api_host": "https://api-us-iot.lepro.com"}
    credential = ClientCredential("client-id", "client-secret")

    result = await async_get_auth_implementation(hass, DOMAIN, credential)

    assert isinstance(result, LoproOAuth2Implementation)
