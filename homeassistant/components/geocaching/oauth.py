"""oAuth2 functions and classes for Geocaching API integration."""
from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, OAUTH2_AUTHORIZE_URL, OAUTH2_TOKEN_URL

_LOGGER = logging.getLogger(__name__)


class GeocachingOAuth2Implementation(
    config_entry_oauth2_flow.LocalOAuth2Implementation
):
    """Local OAuth2 implementation for Geocaching."""

    def __init__(
        self, hass: HomeAssistant, client_id: str, client_secret: str, name: str
    ) -> None:
        """Local Geocaching Oauth Implementation."""
        self._name = name
        super().__init__(
            hass=hass,
            client_id=client_id,
            client_secret=client_secret,
            domain=DOMAIN,
            authorize_url=OAUTH2_AUTHORIZE_URL,
            token_url=OAUTH2_TOKEN_URL,
        )

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return f"{self._name}"

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "*", "response_type": "code"}

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Initialize local Geocaching API auth implementation."""
        redirect_uri = external_data["state"]["redirect_uri"]
        data = {
            "grant_type": "authorization_code",
            "code": external_data["code"],
            "redirect_uri": redirect_uri,
        }
        token = await self._token_request(data)
        # Store the redirect_uri (Needed for refreshing token, but not according to oAuth2 spec!)
        token["redirect_uri"] = redirect_uri
        return token

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            # Add previously stored redirect_uri (Mandatory, but not according to oAuth2 spec!)
            "redirect_uri": token["redirect_uri"],
        }

        new_token = await self._token_request(data)
        return {**token, **new_token}

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        data["client_id"] = self.client_id
        if self.client_secret is not None:
            data["client_secret"] = self.client_secret
        session = async_get_clientsession(self.hass)
        resp = await session.post(OAUTH2_TOKEN_URL, data=data)
        resp.raise_for_status()
        return cast(dict, await resp.json())
