"""application_credentials platform the fitbit integration."""

import base64
import logging
from typing import Any, cast

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN

_LOGGER = logging.getLogger(__name__)


class FitbitOAuth2Implementation(AuthImplementation):
    """Local OAuth2 implementation for Fitbit.

    This implementation is needed to send the client id and secret as a Basic
    Authorization header.
    """

    async def async_resolve_external_data(self, external_data: dict[str, Any]) -> dict:
        """Resolve the authorization code to tokens."""
        session = async_get_clientsession(self.hass)
        data = {
            "grant_type": "authorization_code",
            "code": external_data["code"],
            "redirect_uri": external_data["state"]["redirect_uri"],
        }
        basic_auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {basic_auth}"}
        resp = await session.post(self.token_url, data=data, headers=headers)
        if resp.status >= 400 and _LOGGER.isEnabledFor(logging.DEBUG):
            # await resp.json()
            # Token request failed with status=400, body={"errors":[{"errorType":"invalid_request","message":"Missing 'grant_type' parameter value. Visit https://dev.fitbit.com/docs/oauth2 for more information on the Fitbit Web API authorization process."}],"success":false}
            body = await resp.text()
            _LOGGER.debug(
                "Token request failed with status=%s, body=%s",
                resp.status,
                body,
            )
        resp.raise_for_status()
        return cast(dict, await resp.json())


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
