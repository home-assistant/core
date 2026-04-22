"""Application credentials platform for Heiman."""

from json import JSONDecodeError
import logging
from typing import NoReturn, cast

from aiohttp import BasicAuth, ClientError, ClientResponse, RequestInfo
from yarl import URL

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

from .const import OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL

_LOGGER = logging.getLogger(__name__)


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AuthImplementation:
    """Return auth implementation."""
    return HeimanOAuth2Implementation(
        hass,
        auth_domain,
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

        # Add client_id and client_secret to request body
        request_data = dict(data)
        request_data.setdefault("client_id", self.client_id)
        if self.client_secret:
            request_data.setdefault("client_secret", self.client_secret)

        resp = None
        result: dict | None = None
        try:
            resp = await session.post(
                self.token_url,
                data=request_data,
                auth=BasicAuth(self.client_id, self.client_secret),
            )

            # Check for error status codes
            if resp.status >= 400:
                try:
                    error_response = await resp.json()
                except (ClientError, JSONDecodeError):
                    error_response = {}
                error_code = error_response.get("error", "unknown")
                error_description = error_response.get(
                    "error_description", "unknown error"
                )
                _LOGGER.error(
                    "Token request for %s failed (%s): %s",
                    self.domain,
                    error_code,
                    error_description,
                )

                self._raise_token_error(resp, error_code)

            # Try to parse JSON response
            try:
                result = await self._parse_token_response(resp)
            except OAuth2TokenRequestError:
                raise
            except (ValueError, ClientError, JSONDecodeError) as err:
                _LOGGER.exception("Failed to process token response")
                self._raise_token_error(resp, from_exception=err)
            else:
                # This check should never trigger - result should always be set
                # if no exception was raised
                if result is None:  # pragma: no cover
                    msg = "Unexpected: _token_request completed without returning"
                    raise AssertionError(msg)

                return result

        except OAuth2TokenRequestError:
            # Re-raise OAuth2 errors without modification
            raise
        except ClientError as err:
            _LOGGER.error("Token request for %s failed: %s", self.domain, err)
            # Ensure we always have a valid RequestInfo
            request_info = getattr(err, "request_info", None)
            if request_info is None:
                request_info = RequestInfo(
                    url=URL(self.token_url),
                    method="POST",
                    headers={},  # type: ignore[arg-type]
                    real_url=URL(self.token_url),
                )
            raise OAuth2TokenRequestTransientError(
                request_info=request_info,
                history=getattr(err, "history", ()),
                status=getattr(err, "status", 0),
                headers=getattr(err, "headers", None),
                domain=self.domain,
            ) from err
        except TimeoutError as err:
            _LOGGER.error("Token request for %s timed out: %s", self.domain, err)
            # Create a minimal RequestInfo for the timeout error
            request_info = RequestInfo(
                url=URL(self.token_url),
                method="POST",
                headers={},  # type: ignore[arg-type]
                real_url=URL(self.token_url),
            )
            raise OAuth2TokenRequestTransientError(
                request_info=request_info,
                history=(),
                status=0,
                headers=None,
                domain=self.domain,
            ) from err
        finally:
            # Ensure response is released to avoid connection leaks
            if resp is not None:
                resp.release()

    def _raise_token_error(
        self,
        resp: ClientResponse,
        error_code: str | None = None,
        from_exception: Exception | None = None,
    ) -> NoReturn:
        """Raise appropriate OAuth2 token request error.

        Args:
            resp: HTTP response object
            error_code: Error code from response (optional)
            from_exception: Original exception to chain from (optional)

        Raises:
            OAuth2TokenRequestReauthError: For authentication errors
            OAuth2TokenRequestTransientError: For transient errors
            OAuth2TokenRequestError: For other errors
        """
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
        ) from from_exception

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
