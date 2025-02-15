"""Application credentials platform for SmartThings."""

from json import JSONDecodeError
import logging
from typing import cast

from aiohttp import BasicAuth, ClientError

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return auth implementation."""
    return SmartThingsOAuth2Implementation(
        hass,
        DOMAIN,
        credential,
        authorization_server=AuthorizationServer(
            authorize_url="https://api.smartthings.com/oauth/authorize",
            token_url="https://auth-global.api.smartthings.com/oauth/token",
        ),
    )


class SmartThingsOAuth2Implementation(AuthImplementation):
    """Oauth2 implementation that only uses the external url."""

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)

        resp = await session.post(
            self.token_url,
            data=data,
            auth=BasicAuth(self.client_id, self.client_secret),
        )
        if resp.status >= 400:
            try:
                error_response = await resp.json()
            except (ClientError, JSONDecodeError):
                error_response = {}
            error_code = error_response.get("error", "unknown")
            error_description = error_response.get("error_description", "unknown error")
            _LOGGER.error(
                "Token request for %s failed (%s): %s",
                self.domain,
                error_code,
                error_description,
            )
        resp.raise_for_status()
        return cast(dict, await resp.json())
