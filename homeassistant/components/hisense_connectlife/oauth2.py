"""OAuth2 implementation for Hisense AC Plugin."""

from __future__ import annotations

import logging
import time
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT_ID, CLIENT_SECRET, DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN

_LOGGER = logging.getLogger(__name__)

OAUTH2_CALLBACK_URL = "http://homeassistant.local:8123/auth/external/callback"


class HisenseOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Hisense OAuth2 implementation."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize Hisense OAuth2 implementation."""
        super().__init__(
            hass=hass,
            domain=DOMAIN,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        )
        _LOGGER.debug(
            "Initialized OAuth2 implementation with authorize_url: %s, token_url: %s",
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        )

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        return OAUTH2_CALLBACK_URL

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Hisense AC"

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        _LOGGER.debug(
            "Resolving external data: %s",
            {
                k: "***" if k in ("code", "state") else v
                for k, v in (
                    external_data if isinstance(external_data, dict) else {}
                ).items()
            },
        )
        data = {
            "grant_type": "authorization_code",
            "code": external_data["code"],
            "redirect_uri": external_data["state"]["redirect_uri"],
        }
        return await self._token_request(data)

    async def async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        _LOGGER.debug("Refreshing token")
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": token["refresh_token"],
        }
        new_token = await self._token_request(data)
        return {**token, **new_token}

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        _LOGGER.debug(
            "Making token request with data: %s",
            {
                k: "***" if k in ("code", "client_secret", "refresh_token") else v
                for k, v in data.items()
            },
        )

        session = async_get_clientsession(self.hass)
        data["client_id"] = self.client_id
        data["client_secret"] = self.client_secret
        data["redirect_uri"] = self.redirect_uri

        resp = await session.post(self.token_url, data=data)
        resp.raise_for_status()
        resp_json = cast(dict, await resp.json())

        # Add expires_at to the token response
        if "expires_in" in resp_json and "expires_at" not in resp_json:
            resp_json["expires_at"] = time.time() + resp_json["expires_in"]

        _LOGGER.debug(
            "Token request successful, response: %s",
            {
                k: "***" if k in ("access_token", "refresh_token") else v
                for k, v in resp_json.items()
            },
        )

        return resp_json


class OAuth2Session:
    """OAuth2 session handler."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth2_implementation: HisenseOAuth2Implementation,
        token: dict[str, Any] | None = None,
    ) -> None:
        """Initialize OAuth2 session."""
        self.hass = hass
        self.oauth2_implementation = oauth2_implementation
        self.token = token or {}
        self.session = async_get_clientsession(hass)

        _LOGGER.debug(
            "Initialized OAuth2Session with token info: %s",
            {
                k: "***" if k in ("access_token", "refresh_token") else v
                for k, v in self.token.items()
            },
        )

    async def async_ensure_token_valid(self) -> None:
        """Ensure that the token is valid."""
        if not self.token:
            _LOGGER.error("No token available")
            raise ValueError("No token available")

        if self._is_token_expired():
            _LOGGER.debug("Token has expired, refreshing")
            token_data = await self.oauth2_implementation.async_refresh_token(
                self.token
            )
            self.token.update(token_data)
            _LOGGER.debug("Token refreshed successfully")

    def _is_token_expired(self) -> bool:
        """Check if token is expired."""
        expires_at = self.token.get("expires_at")
        if not expires_at:
            expires_in = self.token.get("expires_in", 0)
            if expires_in:
                self.token["expires_at"] = time.time() + expires_in
                return False
            return True
        return time.time() >= expires_at - 300  # Refresh 5 minutes before expiry

    async def async_get_access_token(self) -> str:
        """Get the access token."""
        await self.async_ensure_token_valid()
        return self.token["access_token"]

    async def close(self) -> None:
        """Close the session."""
        # Session is managed by Home Assistant, no need to close
