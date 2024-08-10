"""application_credentials platform the Weheat integration."""

from json import JSONDecodeError
from typing import cast

from aiohttp import ClientError

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN


class WeheatOAuth2Implementation(LocalOAuth2Implementation):
    """Weheat variant of LocalOAuth2Implementation to support a keycloak specific error message."""

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)

        data["client_id"] = self.client_id

        if self.client_secret is not None:
            data["client_secret"] = self.client_secret

        resp = await session.post(self.token_url, data=data)
        if resp.status >= 400:
            try:
                error_response = await resp.json()
            except (ClientError, JSONDecodeError):
                error_response = {}
            error_code = error_response.get("error", "unknown")
            error_description = error_response.get("error_description", "unknown error")

            # Raise a ConfigEntryAuthFailed as the sessions is no longer valid
            raise ConfigEntryAuthFailed(
                f"Token request for {self.domain} failed ({error_code}): {error_description}"
            )
        resp.raise_for_status()
        return cast(dict, await resp.json())


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return a custom auth implementation."""
    return WeheatOAuth2Implementation(
        hass,
        domain=auth_domain,
        client_id=credential.client_id,
        client_secret=credential.client_secret,
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )
