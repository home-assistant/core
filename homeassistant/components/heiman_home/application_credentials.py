"""Application credentials platform for Heiman."""

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

from .const import DOMAIN, OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL

_LOGGER = logging.getLogger(__name__)


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AuthImplementation:
    """Return auth implementation."""
    return HeimanOAuth2Implementation(
        hass,
        DOMAIN,
        credential,
        authorization_server=AuthorizationServer(
            authorize_url=OAUTH_AUTHORIZE_URL,
            token_url=OAUTH_TOKEN_URL,
        ),
    )


class HeimanOAuth2Implementation(AuthImplementation):
    """OAuth2 implementation for Heiman."""

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)

        resp = await session.post(
            self.token_url,
            data=data,
            auth=BasicAuth(self.client_id, self.client_secret),
        )
        
        # Check for error status codes
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
        
        # Try to parse JSON response
        try:
            # First check if response has content
            text = await resp.text()
            
            if not text or not text.strip():
                _LOGGER.error(
                    "Token request returned empty response (status %s). "
                    "This may indicate an invalid refresh token or expired credentials.",
                    resp.status,
                )
                raise ValueError(f"Empty response from token endpoint (status {resp.status})")
            
            # Try to parse as JSON
            try:
                response_data = await resp.json()
                return cast(dict, response_data)
            except (ClientError, JSONDecodeError) as json_err:
                _LOGGER.error(
                    "Token request returned non-JSON response (status %s, content_type='%s'): %s",
                    resp.status,
                    resp.content_type,
                    text[:500] if text else "(empty)",
                )
                raise
        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as err:
            _LOGGER.error(
                "Failed to process token response: %s",
                err,
                exc_info=True,
            )
            raise
