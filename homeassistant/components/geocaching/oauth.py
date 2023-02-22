"""oAuth2 functions and classes for Geocaching API integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant

from .const import ENVIRONMENT, ENVIRONMENT_URLS


class GeocachingOAuth2Implementation(AuthImplementation):
    """Local OAuth2 implementation for Geocaching."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth_domain: str,
        credential: ClientCredential,
    ) -> None:
        """Local Geocaching Oauth Implementation."""
        super().__init__(
            hass=hass,
            auth_domain=auth_domain,
            credential=credential,
            authorization_server=AuthorizationServer(
                authorize_url=ENVIRONMENT_URLS[ENVIRONMENT]["authorize_url"],
                token_url=ENVIRONMENT_URLS[ENVIRONMENT]["token_url"],
            ),
        )

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
