"""Application credentials platform for Heiman."""

from json import JSONDecodeError
import logging
from typing import cast

from aiohttp import BasicAuth, ClientError, ClientResponse

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
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
    """Heiman-specific OAuth2 implementation.

    This specialization is needed because Heiman's OAuth2 token endpoint
    requires custom error handling and response validation that differs
    from the standard OAuth2 flow. Specifically:
    - Custom error code mapping for re-authentication scenarios
    - Special handling for empty responses (expired refresh tokens)
    - Detailed logging for debugging token issues
    """

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

            # Determine the appropriate exception type based on error code
            if error_code in ["invalid_grant", "invalid_token"]:
                raise OAuth2TokenRequestReauthError(
                    request_info=resp.request_info,
                    history=resp.history,
                    status=resp.status,
                    headers=resp.headers,
                    domain=self.domain,
                )
            if resp.status >= 500:
                raise OAuth2TokenRequestTransientError(
                    request_info=resp.request_info,
                    history=resp.history,
                    status=resp.status,
                    headers=resp.headers,
                    domain=self.domain,
                )
            raise OAuth2TokenRequestError(
                request_info=resp.request_info,
                history=resp.history,
                status=resp.status,
                headers=resp.headers,
                domain=self.domain,
            )

        # Try to parse JSON response
        try:
            return await self._parse_token_response(resp)
        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as err:
            _LOGGER.exception("Failed to process token response: %s", err)
            raise

    async def _parse_token_response(self, resp: ClientResponse) -> dict:
        """Parse and validate token response.

        Args:
            resp: HTTP response object

        Returns:
            Parsed response data as dictionary

        Raises:
            ValueError: If response is empty or invalid
        """
        # First check if response has content
        text = await resp.text()

        if not text or not text.strip():
            _LOGGER.error(
                "Token request returned empty response (status %s). "
                "This may indicate an invalid refresh token or expired credentials",
                resp.status,
            )
            msg = f"Empty response from token endpoint (status {resp.status})"
            raise ValueError(msg)

        # Try to parse as JSON
        try:
            response_data = await resp.json()
            return cast(dict, response_data)
        except (ClientError, JSONDecodeError):
            _LOGGER.exception(
                "Token request returned non-JSON response (status %s, content_type='%s'): %s",
                resp.status,
                resp.content_type,
                text[:500] if text else "(empty)",
            )
            raise
