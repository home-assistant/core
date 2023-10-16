"""application_credentials platform for Withings."""

from typing import Any

from aiowithings import AUTHORIZATION_URL, TOKEN_URL

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation."""
    return WithingsLocalOAuth2Implementation(
        hass,
        DOMAIN,
        credential,
        authorization_server=AuthorizationServer(
            authorize_url=AUTHORIZATION_URL,
            token_url=TOKEN_URL,
        ),
    )


class WithingsLocalOAuth2Implementation(AuthImplementation):
    """Oauth2 implementation that only uses the external url."""

    async def _token_request(self, data: dict) -> dict:
        """Make a token request and adapt Withings API reply."""
        new_token = await super()._token_request(data)
        # Withings API returns habitual token data under json key "body":
        # {
        #     "status": [{integer} Withings API response status],
        #     "body": {
        #         "access_token": [{string} Your new access_token],
        #         "expires_in": [{integer} Access token expiry delay in seconds],
        #         "token_type": [{string] HTTP Authorization Header format: Bearer],
        #         "scope": [{string} Scopes the user accepted],
        #         "refresh_token": [{string} Your new refresh_token],
        #         "userid": [{string} The Withings ID of the user]
        #     }
        # }
        # so we copy that to token root.
        if body := new_token.pop("body", None):
            new_token.update(body)
        return new_token

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        return await self._token_request(
            {
                "action": "requesttoken",
                "grant_type": "authorization_code",
                "code": external_data["code"],
                "redirect_uri": external_data["state"]["redirect_uri"],
            }
        )

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        new_token = await self._token_request(
            {
                "action": "requesttoken",
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": token["refresh_token"],
            }
        )
        return {**token, **new_token}
