"""Xthings Cloud browser SSO callback."""

import json
import time
from collections.abc import Mapping
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from aiohttp import web
from ha_xthings_cloud import XthingsCloudApiClient, XthingsCloudApiError
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth_util import async_user_not_allowed_do_auth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.http import KEY_HASS
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from .const import DOMAIN, LOGGER

SSO_URL = "/api/xthings_cloud/sso/callback"
SSO_CLIENT_NAME = "Xthings Cloud SSO"
SSO_ACCESS_TOKEN_EXPIRATION = timedelta(minutes=5)


def _bridge_html(tokens: Mapping[str, Any]) -> str:
    """Return a same-origin bridge that hands tokens to the HA frontend."""
    token_json = json.dumps(tokens, separators=(",", ":")).replace("<", "\\u003c")
    return (
        '<!doctype html><meta charset="utf-8">'
        "<title>Signing in</title><script>"
        f"localStorage.setItem('hassTokens', JSON.stringify({token_json}));"
        "window.location.replace('/');"
        "</script>"
    )


def _error(error_type: type[web.HTTPException], message: str) -> web.Response:
    """Return a non-cacheable error response."""
    return web.Response(
        status=error_type.status_code,
        text=message,
        headers={"Cache-Control": "no-store"},
    )


class XthingsSsoManager:
    """Exchange Cloud SSO codes and create short-lived HA sessions."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: XthingsCloudApiClient
    ) -> None:
        """Initialize the SSO manager."""
        self.hass = hass
        self.entry = entry
        self.client = client
        self._session_user_id: str | None = None

    async def async_create_bridge(
        self, request: web.Request, code: str
    ) -> web.Response:
        """Exchange a one-time Cloud code and create a browser session."""
        if not code:
            return _error(web.HTTPUnauthorized, "Invalid SSO code")

        instance_id = await async_get_instance_id(self.hass)
        try:
            exchange = await self.client.async_exchange_sso_code(code, instance_id)
        except (XthingsCloudApiError, TimeoutError):
            LOGGER.warning("Xthings SSO code exchange failed")
            return _error(web.HTTPUnauthorized, "Invalid SSO code")
        if (
            exchange.get("instance_id") != instance_id
            or exchange.get("user_uuid") != self.entry.unique_id
            or not isinstance(exchange.get("sso_ha_user_id"), str)
        ):
            return _error(web.HTTPUnauthorized, "Invalid SSO code")

        user_id = exchange["sso_ha_user_id"]
        self._session_user_id = user_id
        user = await self.hass.auth.async_get_user(user_id)
        if user is None or not user.is_active:
            return _error(web.HTTPForbidden, "HA user is unavailable")
        if error := async_user_not_allowed_do_auth(self.hass, user, request):
            return _error(web.HTTPForbidden, error)

        origin = self._origin(request)
        client_id = f"{origin}/"
        refresh_token = await self.hass.auth.async_create_refresh_token(
            user,
            client_id=client_id,
            client_name=SSO_CLIENT_NAME,
            access_token_expiration=SSO_ACCESS_TOKEN_EXPIRATION,
        )
        # Do not bind the browser token to the proxy's source IP; websocket requests may use a different proxy path.
        access_token = self.hass.auth.async_create_access_token(refresh_token)
        LOGGER.info("Xthings SSO session created for user %s at %s", user.id, origin)
        tokens = {
            "access_token": access_token,
            "token_type": "Bearer",
            "refresh_token": refresh_token.token,
            "expires": int(time.time() * 1000)
            + int(SSO_ACCESS_TOKEN_EXPIRATION.total_seconds() * 1000),
            "hassUrl": origin,
            "clientId": client_id,
        }
        return web.Response(
            text=_bridge_html(tokens),
            content_type="text/html",
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'",
                "Referrer-Policy": "no-referrer",
            },
        )

    def _origin(self, request: web.Request) -> str:
        """Return the browser-visible origin used by the HA frontend."""
        external_url = self.hass.config.external_url
        if external_url:
            parsed = urlsplit(external_url)
            return urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, "", "")
            ).rstrip("/")
        forwarded_proto = (
            request.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip()
        )
        scheme = forwarded_proto or request.scheme
        return f"{scheme}://{request.host}"

    async def async_revoke_sessions(self) -> None:
        """Revoke refresh tokens created by the SSO bridge."""
        if not self._session_user_id:
            return
        user = await self.hass.auth.async_get_user(self._session_user_id)
        if user is None:
            return
        for refresh_token in list(user.refresh_tokens.values()):
            if refresh_token.client_name == SSO_CLIENT_NAME:
                self.hass.auth.async_remove_refresh_token(refresh_token)


class XthingsSsoView(HomeAssistantView):
    """Accept a one-time Cloud code and return the same-origin bridge."""

    url = SSO_URL
    name = "api:xthings_cloud:sso_callback"
    requires_auth = False
    cors_allowed = False

    async def get(self, request: web.Request) -> web.Response:
        """Handle a browser callback from Xthings Cloud."""
        hass = request.app[KEY_HASS]
        manager: XthingsSsoManager | None = hass.data.get(DOMAIN, {}).get("sso")
        if manager is None:
            return _error(web.HTTPServiceUnavailable, "SSO unavailable")
        return await manager.async_create_bridge(request, request.query.get("code", ""))
