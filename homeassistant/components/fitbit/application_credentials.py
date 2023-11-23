"""application_credentials platform the fitbit integration.

See https://dev.fitbit.com/build/reference/web-api/authorization/ for additional
details on Fitbit authorization.
"""

import base64
from http import HTTPStatus
import logging
from typing import Any, cast

import aiohttp

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from .exceptions import FitbitApiException, FitbitAuthException

_LOGGER = logging.getLogger(__name__)


class FitbitOAuth2Implementation(AuthImplementation):
    """Local OAuth2 implementation for Fitbit.

    This implementation is needed to send the client id and secret as a Basic
    Authorization header.
    """

    async def async_resolve_external_data(self, external_data: dict[str, Any]) -> dict:
        """Resolve the authorization code to tokens."""
        return await self._post(
            {
                "grant_type": "authorization_code",
                "code": external_data["code"],
                "redirect_uri": external_data["state"]["redirect_uri"],
            }
        )

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        return await self._post(
            {
                **data,
                CONF_CLIENT_ID: self.client_id,
                CONF_CLIENT_SECRET: self.client_secret,
            }
        )

    async def _post(self, data: dict[str, Any]) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        try:
            resp = await session.post(self.token_url, data=data, headers=self._headers)
            resp.raise_for_status()
        except aiohttp.ClientResponseError as err:
            if _LOGGER.isEnabledFor(logging.DEBUG):
                error_body = await resp.text() if not session.closed else ""
                _LOGGER.debug(
                    "Client response error status=%s, body=%s", err.status, error_body
                )
            if err.status == HTTPStatus.UNAUTHORIZED:
                raise FitbitAuthException(f"Unauthorized error: {err}") from err
            raise FitbitApiException(f"Server error response: {err}") from err
        except aiohttp.ClientError as err:
            raise FitbitApiException(f"Client connection error: {err}") from err
        return cast(dict, await resp.json())

    @property
    def _headers(self) -> dict[str, str]:
        """Build necessary authorization headers."""
        basic_auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        return {"Authorization": f"Basic {basic_auth}"}


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return a custom auth implementation."""
    return FitbitOAuth2Implementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        ),
    )
