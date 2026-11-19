"""Application credentials platform for the Untappd integration."""

from typing import Any, override

from aiountappd import UntappdError, async_get_access_token

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestConnectionError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation

from .const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN, TOKEN_EXPIRES_IN


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return auth implementation."""
    return UntappdOAuth2Implementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(authorize_url=OAUTH2_AUTHORIZE, token_url=OAUTH2_TOKEN),
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "developer_url": "https://untappd.com/api/register",
        "more_info_url": "https://www.home-assistant.io/integrations/untappd/",
    }


class UntappdOAuth2Implementation(AuthImplementation):
    """Untappd OAuth2 implementation.

    Untappd names the redirect parameter `redirect_url`, exchanges the code with a
    GET request, and issues access tokens that never expire.
    """

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Add the redirect parameter under the name Untappd expects."""
        return {"redirect_url": self.redirect_uri}

    @override
    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Exchange the authorization code for an access token."""
        try:
            access_token = await async_get_access_token(
                async_get_clientsession(self.hass),
                self.client_id,
                self.client_secret,
                external_data["state"]["redirect_uri"],
                external_data["code"],
            )
        except UntappdError as err:
            raise OAuth2TokenRequestConnectionError(domain=self.domain) from err
        return {"access_token": access_token, "expires_in": TOKEN_EXPIRES_IN}

    @override
    async def _async_refresh_token(self, token: dict) -> dict:
        """Return the token unchanged, Untappd tokens do not expire."""
        return token
